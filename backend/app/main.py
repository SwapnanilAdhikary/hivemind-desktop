from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, desc

from app.config import settings
from app.db.database import init_db, get_session, async_session
from app.db.models import Message, Trace, Decision, Tool, PlatformStatus
from app.websocket.manager import ws_manager
from app.llm.router import llm_router
from app.llm.ollama_provider import check_ollama_available, list_ollama_models
from app.llm.api_provider import is_openai_configured, is_anthropic_configured
from app.tools.registry import tool_registry
from app.tools.tool_creator import create_tool
from app.agents.orchestrator import orchestrator, AgentState
from app.agents.gmail_agent import gmail_agent
from app.agents.whatsapp_agent import whatsapp_agent
from app.agents.discord_agent import discord_agent
from app.agents.instagram_agent import instagram_agent
from app.tracing.tracer import new_run_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    await init_db()
    logger.info("Database initialized")

    _background_tasks.append(asyncio.create_task(_safe_start(gmail_agent.start(), "Gmail")))
    _background_tasks.append(asyncio.create_task(_safe_start(whatsapp_agent.start(), "WhatsApp")))
    _background_tasks.append(asyncio.create_task(_safe_start(discord_agent.start(), "Discord")))
    _background_tasks.append(asyncio.create_task(_safe_start(instagram_agent.start(), "Instagram")))

    yield

    for task in _background_tasks:
        task.cancel()
    logger.info("Background tasks cancelled")


async def _safe_start(coro, name: str):
    """Run an agent coroutine with error isolation."""
    try:
        await coro
    except asyncio.CancelledError:
        logger.info("%s agent stopped", name)
    except Exception as e:
        logger.error("%s agent crashed: %s", name, e)


app = FastAPI(title="Unified Agent Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("WS received: %s", data[:200])
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    ollama_ok = await check_ollama_available()
    return {
        "status": "ok",
        "ollama_available": ollama_ok,
        "openai_configured": is_openai_configured(),
        "anthropic_configured": is_anthropic_configured(),
        "websocket_clients": ws_manager.active_count,
    }


@app.get("/api/llm/models")
async def list_models():
    models = {"ollama": [], "openai": [], "anthropic": []}
    models["ollama"] = await list_ollama_models()
    if is_openai_configured():
        models["openai"] = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
    if is_anthropic_configured():
        models["anthropic"] = ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]
    return models


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class IncomingMessage(BaseModel):
    platform: str
    sender: str
    sender_name: str = ""
    content: str
    conversation_id: str = ""
    metadata: dict[str, Any] = {}


@app.post("/api/messages/incoming")
async def receive_message(msg: IncomingMessage):
    """Receive a message from any platform integration and run it through the orchestrator."""
    async with async_session() as session:
        db_msg = Message(
            platform=msg.platform,
            sender=msg.sender,
            sender_name=msg.sender_name,
            content=msg.content,
            conversation_id=msg.conversation_id,
            metadata_json=msg.metadata,
        )
        session.add(db_msg)
        await session.commit()
        await session.refresh(db_msg)

    run_id = new_run_id()
    state: AgentState = {
        "run_id": run_id,
        "platform": msg.platform,
        "sender": msg.sender,
        "sender_name": msg.sender_name,
        "content": msg.content,
        "conversation_id": msg.conversation_id,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": msg.metadata,
    }

    try:
        result = await orchestrator.ainvoke(state)
        return {
            "message_id": db_msg.id,
            "run_id": run_id,
            "action": result.get("action", "notify"),
            "urgency": result.get("urgency", "medium"),
            "draft_reply": result.get("draft_reply", ""),
        }
    except Exception as e:
        logger.error("Orchestrator error: %s", e)
        await ws_manager.broadcast("new_message", {
            "platform": msg.platform,
            "sender": msg.sender,
            "content": msg.content[:200],
            "urgency": "medium",
            "action": "notify",
            "error": str(e),
        })
        return {"message_id": db_msg.id, "run_id": run_id, "error": str(e)}


@app.get("/api/messages")
async def list_messages(platform: str | None = None, limit: int = 50, offset: int = 0):
    async with async_session() as session:
        stmt = select(Message).order_by(desc(Message.timestamp)).limit(limit).offset(offset)
        if platform:
            stmt = stmt.where(Message.platform == platform)
        result = await session.execute(stmt)
        messages = result.scalars().all()
        return [
            {
                "id": m.id,
                "platform": m.platform,
                "sender": m.sender,
                "sender_name": m.sender_name,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "read": m.read,
                "replied": m.replied,
                "conversation_id": m.conversation_id,
            }
            for m in messages
        ]


class ReplyRequest(BaseModel):
    message_id: int
    reply_content: str


@app.post("/api/messages/reply")
async def send_reply(req: ReplyRequest):
    """User approves and sends a reply."""
    async with async_session() as session:
        result = await session.execute(select(Message).where(Message.id == req.message_id))
        msg = result.scalar_one_or_none()
        if not msg:
            raise HTTPException(404, "Message not found")
        msg.replied = True
        msg.reply_content = req.reply_content
        await session.commit()

    await ws_manager.broadcast("reply_sent", {
        "message_id": req.message_id,
        "platform": msg.platform,
        "sender": msg.sender,
        "reply": req.reply_content,
    })
    return {"status": "sent", "message_id": req.message_id}


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

@app.get("/api/traces")
async def list_traces(limit: int = 100, offset: int = 0):
    async with async_session() as session:
        stmt = select(Trace).order_by(desc(Trace.timestamp)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        traces = result.scalars().all()
        return [
            {
                "id": t.id,
                "run_id": t.run_id,
                "agent_name": t.agent_name,
                "node_name": t.node_name,
                "input_state": t.input_state,
                "output_state": t.output_state,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "duration_ms": t.duration_ms,
            }
            for t in traces
        ]


@app.get("/api/traces/{run_id}")
async def get_trace_by_run(run_id: str):
    async with async_session() as session:
        stmt = select(Trace).where(Trace.run_id == run_id).order_by(Trace.timestamp)
        result = await session.execute(stmt)
        traces = result.scalars().all()

        decisions_stmt = select(Decision).where(
            Decision.trace_id.in_([t.id for t in traces])
        )
        dec_result = await session.execute(decisions_stmt)
        decisions = dec_result.scalars().all()

        return {
            "run_id": run_id,
            "traces": [
                {
                    "id": t.id,
                    "node_name": t.node_name,
                    "agent_name": t.agent_name,
                    "input_state": t.input_state,
                    "output_state": t.output_state,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    "duration_ms": t.duration_ms,
                }
                for t in traces
            ],
            "decisions": [
                {
                    "id": d.id,
                    "node_name": d.node_name,
                    "reasoning": d.reasoning,
                    "chosen_action": d.chosen_action,
                    "alternatives": d.alternatives,
                }
                for d in decisions
            ],
        }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class RegisterToolRequest(BaseModel):
    name: str
    description: str
    source_code: str
    parameters_schema: dict = {}


@app.get("/api/tools")
async def list_tools():
    return await tool_registry.list_tools(enabled_only=False)


@app.post("/api/tools")
async def register_tool(req: RegisterToolRequest):
    tool_id = await tool_registry.register(
        name=req.name,
        description=req.description,
        source_code=req.source_code,
        parameters_schema=req.parameters_schema,
    )
    return {"id": tool_id, "name": req.name}


class ExecuteToolRequest(BaseModel):
    name: str
    arguments: dict = {}


@app.post("/api/tools/execute")
async def execute_tool(req: ExecuteToolRequest):
    try:
        result = await tool_registry.execute_tool(req.name, req.arguments)
        return {"result": result}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/api/tools/{name}")
async def delete_tool(name: str):
    ok = await tool_registry.delete_tool(name)
    if not ok:
        raise HTTPException(404, "Tool not found")
    return {"status": "deleted"}


@app.patch("/api/tools/{name}/toggle")
async def toggle_tool(name: str, enabled: bool = True):
    ok = await tool_registry.toggle_tool(name, enabled)
    if not ok:
        raise HTTPException(404, "Tool not found")
    return {"status": "toggled", "enabled": enabled}


class CreateToolRequest(BaseModel):
    task_description: str


@app.post("/api/tools/create")
async def create_tool_endpoint(req: CreateToolRequest):
    """Use the AI tool creator agent to generate and register a new tool."""
    result = await create_tool(req.task_description)
    if not result["success"]:
        raise HTTPException(400, result.get("error") or result.get("validation_result", "Failed"))
    return result


# ---------------------------------------------------------------------------
# Platform Agents Control
# ---------------------------------------------------------------------------

@app.post("/api/platforms/{platform}/reply")
async def platform_reply(platform: str, req: ReplyRequest):
    """Send a reply through a specific platform agent."""
    async with async_session() as session:
        result = await session.execute(select(Message).where(Message.id == req.message_id))
        msg = result.scalar_one_or_none()
        if not msg:
            raise HTTPException(404, "Message not found")

    conversation_id = msg.conversation_id
    try:
        if platform == "gmail":
            metadata = msg.metadata_json or {}
            await gmail_agent.send_reply(
                thread_id=metadata.get("thread_id", conversation_id),
                to=msg.sender,
                subject=metadata.get("subject", ""),
                body=req.reply_content,
            )
        elif platform == "whatsapp":
            await whatsapp_agent.send_reply(conversation_id, req.reply_content)
        elif platform == "discord":
            await discord_agent.send_reply(conversation_id, req.reply_content)
        elif platform == "instagram":
            await instagram_agent.send_reply(conversation_id, req.reply_content)
        else:
            raise HTTPException(400, f"Unknown platform: {platform}")

        async with async_session() as session:
            result = await session.execute(select(Message).where(Message.id == req.message_id))
            row = result.scalar_one_or_none()
            if row:
                row.replied = True
                row.reply_content = req.reply_content
                await session.commit()

        return {"status": "sent", "platform": platform}
    except Exception as e:
        raise HTTPException(500, f"Reply failed: {e}")


# ---------------------------------------------------------------------------
# Platform Status
# ---------------------------------------------------------------------------

@app.get("/api/platforms/status")
async def platform_status():
    async with async_session() as session:
        result = await session.execute(select(PlatformStatus))
        rows = result.scalars().all()
        if not rows:
            platforms = ["gmail", "whatsapp", "instagram", "discord"]
            for p in platforms:
                session.add(PlatformStatus(platform=p, connected=False))
            await session.commit()
            result = await session.execute(select(PlatformStatus))
            rows = result.scalars().all()
        return [
            {
                "platform": r.platform,
                "connected": r.connected,
                "last_checked": r.last_checked.isoformat() if r.last_checked else None,
                "error_message": r.error_message,
            }
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Graph Definition (for frontend visualization)
# ---------------------------------------------------------------------------

@app.get("/api/graph/definition")
async def graph_definition():
    """Return the orchestrator graph structure for the React Flow visualizer."""
    return {
        "nodes": [
            {"id": "classify_message", "label": "Classify Message", "type": "process"},
            {"id": "check_urgency", "label": "Check Urgency", "type": "process"},
            {"id": "decide_action", "label": "Decide Action", "type": "decision"},
            {"id": "draft_reply", "label": "Draft Reply", "type": "process"},
            {"id": "send_reply", "label": "Send Reply", "type": "output"},
            {"id": "notify_user", "label": "Notify User", "type": "output"},
            {"id": "__end__", "label": "End", "type": "end"},
        ],
        "edges": [
            {"source": "classify_message", "target": "check_urgency"},
            {"source": "check_urgency", "target": "decide_action", "label": "all"},
            {"source": "decide_action", "target": "draft_reply", "label": "auto_reply"},
            {"source": "decide_action", "target": "notify_user", "label": "notify/queue"},
            {"source": "decide_action", "target": "__end__", "label": "ignore"},
            {"source": "draft_reply", "target": "send_reply"},
            {"source": "send_reply", "target": "notify_user"},
            {"source": "notify_user", "target": "__end__"},
        ],
    }
