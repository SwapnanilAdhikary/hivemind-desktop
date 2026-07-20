from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.llm.router import llm_router
from app.tracing.tracer import TracingContext, new_run_id
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


WHATSAPP_SYSTEM_PROMPT = (
    "You are a WhatsApp auto-reply assistant. Reply in 1-2 short sentences max. "
    "Be direct and useful. Answer the question or acknowledge the message. "
    "No greetings, no sign-offs, no markdown, no bullet lists, no thinking out loud. "
    "Output only the reply text the user should receive."
)


def _clean_reply(text: str) -> str:
    """Strip model thinking blocks and trim whitespace."""
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<thinking>[\s\S]*?</thinking>", "", text, flags=re.IGNORECASE)
    return text.strip()


def _extract_keyword(text: str, options: tuple[str, ...], default: str) -> str:
    """Find the first expected keyword in a (possibly verbose) LLM response."""
    lowered = text.lower()
    if lowered.strip() in options:
        return lowered.strip()
    for opt in options:
        if opt in lowered:
            return opt
    return default


class AgentState(TypedDict, total=False):
    run_id: str
    platform: str
    sender: str
    sender_name: str
    content: str
    conversation_id: str
    timestamp: str
    message_type: str
    urgency: str
    action: str
    draft_reply: str
    approved: bool
    metadata: dict[str, Any]
    error: str


# ---------------------------------------------------------------------------
# Node functions -- each logs full LLM I/O into traces
# ---------------------------------------------------------------------------

async def classify_message(state: AgentState) -> AgentState:
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "orchestrator", "classify_message") as ctx:
        llm = llm_router.get_llm()
        prompt = (
            f"Classify this message from {state['platform']}.\n"
            f"Sender: {state.get('sender_name', state['sender'])}\n"
            f"Content: {state['content'][:500]}\n\n"
            "Return a JSON with: message_type (email/chat/dm/mention), "
            "a one-line summary, and any detected intent."
        )
        ctx.set_input(
            prompt=prompt,
            platform=state["platform"],
            sender=state.get("sender_name", state["sender"]),
            message_preview=state["content"][:300],
        )
        try:
            result = await llm.ainvoke([{"role": "user", "content": prompt}])
            llm_response = result.content
            state["message_type"] = state.get("message_type", "chat")
            ctx.set_output(
                llm_response=llm_response,
                message_type=state["message_type"],
            )
            await ctx.record_decision(
                reasoning=f"LLM classified message: {llm_response[:300]}",
                chosen=state["message_type"],
                alternatives=["email", "chat", "dm", "mention"],
            )
        except Exception as e:
            logger.error("Classification failed: %s", e)
            state["error"] = str(e)
            ctx.set_output(error=str(e))
    return state


async def check_urgency(state: AgentState) -> AgentState:
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "orchestrator", "check_urgency") as ctx:
        llm = llm_router.get_llm()
        prompt = (
            f"Rate the urgency of this message as high, medium, or low.\n"
            f"Platform: {state['platform']}\n"
            f"From: {state.get('sender_name', state['sender'])}\n"
            f"Content: {state['content'][:500]}\n\n"
            "Respond with just one word: high, medium, or low."
        )
        ctx.set_input(
            prompt=prompt,
            platform=state["platform"],
            sender=state.get("sender_name", state["sender"]),
        )
        try:
            result = await llm.ainvoke([{"role": "user", "content": prompt}])
            llm_response = _clean_reply(result.content)
            urgency = _extract_keyword(llm_response, ("high", "medium", "low"), default="medium")
            state["urgency"] = urgency
            ctx.set_output(
                llm_raw_response=llm_response,
                urgency=urgency,
            )
            await ctx.record_decision(
                reasoning=f"LLM rated urgency as '{llm_response}'. Normalized to '{urgency}'.",
                chosen=urgency,
                alternatives=["high", "medium", "low"],
            )
        except Exception as e:
            logger.error("Urgency check failed: %s", e)
            state["urgency"] = "medium"
            ctx.set_output(error=str(e), urgency="medium (fallback)")
    return state


async def decide_action(state: AgentState) -> AgentState:
    run_id = state.get("run_id", new_run_id())
    metadata = state.get("metadata", {})
    is_group = metadata.get("is_group", False)

    # Never auto-reply to group chats
    if is_group:
        async with TracingContext(run_id, "orchestrator", "decide_action") as ctx:
            state["action"] = "notify"
            ctx.set_input(is_group=True, platform=state["platform"], sender=state.get("sender_name", ""))
            ctx.set_output(chosen_action="notify", reasoning="Group chat -- auto-reply disabled")
            await ctx.record_decision(
                reasoning="Message is from a group chat. Auto-reply is disabled for groups.",
                chosen="notify",
                alternatives=["auto_reply", "ignore"],
            )
        return state

    async with TracingContext(run_id, "orchestrator", "decide_action") as ctx:
        llm = llm_router.get_llm()
        prompt = (
            f"Given this {state['urgency']} urgency message from {state['platform']}:\n"
            f"From: {state.get('sender_name', state['sender'])}\n"
            f"Content: {state['content'][:500]}\n\n"
            "What action should the AI assistant take?\n"
            "Options: auto_reply (respond automatically), notify (just alert the user without replying), "
            "ignore (spam/irrelevant)\n\n"
            "For personal messages, chats and DMs, prefer auto_reply.\n"
            "Only use notify for complex emails or topics needing human judgment.\n"
            "Only use ignore for clear spam.\n"
            "Respond with just the action word."
        )
        ctx.set_input(
            prompt=prompt,
            urgency=state["urgency"],
            platform=state["platform"],
            sender=state.get("sender_name", state["sender"]),
            message_preview=state["content"][:200],
        )
        try:
            result = await llm.ainvoke([{"role": "user", "content": prompt}])
            llm_response = _clean_reply(result.content)
            valid = {"auto_reply", "notify", "queue", "ignore"}
            action = _extract_keyword(
                llm_response.replace(" ", "_"),
                ("auto_reply", "queue", "ignore", "notify"),
                default="notify",
            )
            state["action"] = action
            ctx.set_output(
                llm_raw_response=llm_response,
                chosen_action=action,
                reasoning=f"Message urgency is {state['urgency']} from {state['platform']}. "
                          f"LLM chose '{action}' for message: '{state['content'][:100]}'",
            )
            await ctx.record_decision(
                reasoning=f"Urgency={state['urgency']}, platform={state['platform']}, "
                          f"sender={state.get('sender_name', '')}. "
                          f"LLM response: '{llm_response}'. Chose '{action}'.",
                chosen=action,
                alternatives=list(valid - {action}),
            )
        except Exception as e:
            logger.error("Action decision failed: %s", e)
            state["action"] = "notify"
            ctx.set_output(error=str(e), chosen_action="notify (fallback)")
    return state


def action_router(state: AgentState) -> str:
    action = state.get("action", "notify")
    if action == "auto_reply":
        return "draft_reply"
    elif action == "ignore":
        return END
    else:
        return "notify_user"


async def draft_reply(state: AgentState) -> AgentState:
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "orchestrator", "draft_reply") as ctx:
        llm = llm_router.get_llm()
        platform = state["platform"]
        sender = state.get("sender_name", state["sender"])
        content = state["content"][:500]

        if platform == "whatsapp":
            messages = [
                {"role": "system", "content": WHATSAPP_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"From: {sender}\nMessage: {content}\n\nReply:",
                },
            ]
            prompt = messages[1]["content"]
        else:
            prompt = (
                f"Draft a helpful reply to this message on {platform}.\n"
                f"From: {sender}\n"
                f"Message: {content}\n\n"
                "Write a concise, friendly reply."
            )
            messages = [{"role": "user", "content": prompt}]

        ctx.set_input(
            prompt=prompt,
            platform=platform,
            sender=sender,
            original_message=state["content"][:300],
        )
        try:
            result = await llm.ainvoke(messages)
            reply = _clean_reply(result.content or "")
            state["draft_reply"] = reply
            ctx.set_output(
                draft_reply=reply,
                reply_length=len(reply),
            )
            await ctx.record_decision(
                reasoning=f"Drafted reply ({len(reply)} chars) for {platform} "
                          f"message from {sender}",
                chosen="reply_drafted",
                alternatives=[],
            )
        except Exception as e:
            logger.error("Reply drafting failed: %s", e)
            state["draft_reply"] = ""
            state["action"] = "notify"
            ctx.set_output(error=str(e))
    return state


async def notify_user(state: AgentState) -> AgentState:
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "orchestrator", "notify_user") as ctx:
        metadata = state.get("metadata", {})
        notification = {
            "id": metadata.get("db_message_id"),
            "platform": state["platform"],
            "sender": state["sender"],
            "sender_name": state.get("sender_name", ""),
            "content": state["content"][:200],
            "conversation_id": state.get("conversation_id", ""),
            "urgency": state.get("urgency", "medium"),
            "action": state.get("action", "notify"),
            "draft_reply": state.get("draft_reply", ""),
            "timestamp": state.get("timestamp", datetime.utcnow().isoformat()),
        }
        ctx.set_input(action=state.get("action"), urgency=state.get("urgency"))
        ctx.set_output(
            notified=True,
            has_draft_reply=bool(state.get("draft_reply")),
            action_taken=state.get("action", "notify"),
        )
        await ws_manager.broadcast("new_message", notification)
    return state


async def send_reply(state: AgentState) -> AgentState:
    run_id = state.get("run_id", new_run_id())
    async with TracingContext(run_id, "orchestrator", "send_reply") as ctx:
        platform = state["platform"]
        reply_text = state.get("draft_reply", "")
        conversation_id = state.get("conversation_id", "")
        metadata = state.get("metadata", {})

        ctx.set_input(
            platform=platform,
            reply_preview=reply_text[:300],
            conversation_id=conversation_id,
            recipient=state.get("sender_name", state["sender"]),
        )

        if not reply_text:
            ctx.set_output(sent=False, reason="Empty reply text")
            return state

        try:
            if platform == "whatsapp":
                from app.integrations.whatsapp_bridge import whatsapp_bridge
                await whatsapp_bridge.send_message(conversation_id, reply_text)
            elif platform == "discord":
                from app.integrations.discord_client import discord_client
                await discord_client.send_reply(int(conversation_id), reply_text)
            elif platform == "instagram":
                from app.integrations.instagram_client import instagram_client
                import asyncio
                await asyncio.to_thread(instagram_client.send_dm, conversation_id, reply_text)
            elif platform == "gmail":
                from app.integrations.gmail_client import gmail_client
                import asyncio
                await asyncio.to_thread(
                    gmail_client.send_reply,
                    metadata.get("thread_id", conversation_id),
                    state["sender"],
                    metadata.get("subject", ""),
                    reply_text,
                )

            db_msg_id = metadata.get("db_message_id")
            if db_msg_id:
                from app.db.database import async_session
                from app.db.models import Message
                from sqlalchemy import select
                async with async_session() as session:
                    result = await session.execute(select(Message).where(Message.id == db_msg_id))
                    row = result.scalar_one_or_none()
                    if row:
                        row.replied = True
                        row.reply_content = reply_text
                        await session.commit()

            logger.info("Auto-reply sent on %s to %s", platform, state.get("sender_name", state["sender"]))
            ctx.set_output(
                sent=True,
                platform=platform,
                reply_sent=reply_text[:200],
            )
            await ctx.record_decision(
                reasoning=f"Successfully sent auto-reply on {platform} to "
                          f"{state.get('sender_name', state['sender'])}",
                chosen="reply_sent",
                alternatives=[],
            )
            await ws_manager.broadcast("reply_sent", {
                "platform": platform,
                "sender": state["sender"],
                "reply": reply_text,
            })
        except Exception as e:
            logger.error("Failed to send auto-reply on %s: %s", platform, e)
            ctx.set_output(sent=False, error=str(e))

    return state


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_orchestrator() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("classify_message", classify_message)
    graph.add_node("check_urgency", check_urgency)
    graph.add_node("decide_action", decide_action)
    graph.add_node("draft_reply", draft_reply)
    graph.add_node("notify_user", notify_user)
    graph.add_node("send_reply", send_reply)

    graph.set_entry_point("classify_message")
    graph.add_edge("classify_message", "check_urgency")
    graph.add_edge("check_urgency", "decide_action")
    graph.add_conditional_edges("decide_action", action_router, {
        "draft_reply": "draft_reply",
        "notify_user": "notify_user",
        END: END,
    })
    graph.add_edge("draft_reply", "send_reply")
    graph.add_edge("send_reply", "notify_user")
    graph.add_edge("notify_user", END)

    return graph.compile()


orchestrator = build_orchestrator()
