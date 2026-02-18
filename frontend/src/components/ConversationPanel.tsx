import { useState } from "react";
import { useAgentStore, type PlatformMessage } from "@/stores/agentStore";
import { cn, PLATFORM_COLORS, apiFetch } from "@/lib/utils";
import { Send, Mail, MessageCircle, Instagram, Hash } from "lucide-react";

const PLATFORM_ICONS: Record<string, React.ElementType> = {
  gmail: Mail,
  whatsapp: MessageCircle,
  instagram: Instagram,
  discord: Hash,
};

export default function ConversationPanel() {
  const { messages } = useAgentStore();
  const [selected, setSelected] = useState<PlatformMessage | null>(null);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);

  const unreplied = messages.filter((m) => !m.replied && m.type !== "reply_sent");

  const handleReply = async () => {
    if (!selected || !replyText.trim()) return;
    setSending(true);
    try {
      if (selected.id) {
        await apiFetch(`/api/platforms/${selected.platform}/reply`, {
          method: "POST",
          body: JSON.stringify({ message_id: selected.id, reply_content: replyText }),
        });
      } else {
        // Message arrived via WebSocket without DB id -- fetch latest messages to find it
        const msgs = await apiFetch<any[]>(`/api/messages?platform=${selected.platform}&limit=20`);
        const match = msgs.find(
          (m: any) => m.sender === selected.sender && m.content === selected.content
        );
        if (match) {
          await apiFetch(`/api/platforms/${selected.platform}/reply`, {
            method: "POST",
            body: JSON.stringify({ message_id: match.id, reply_content: replyText }),
          });
        }
      }
      setReplyText("");
      setSelected(null);
    } catch (e) {
      console.error("Reply failed:", e);
    }
    setSending(false);
  };

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-4">
      {/* Message list */}
      <div className="w-80 shrink-0 space-y-2 overflow-auto rounded-xl border border-surface-800 bg-surface-900 p-3">
        <h3 className="mb-2 text-sm font-medium text-surface-400">Inbox ({unreplied.length})</h3>
        {unreplied.length === 0 && (
          <p className="py-8 text-center text-sm text-surface-500">All caught up</p>
        )}
        {unreplied.map((msg, i) => {
          const Icon = PLATFORM_ICONS[msg.platform] ?? Mail;
          const color = PLATFORM_COLORS[msg.platform] ?? "#6366f1";
          return (
            <button
              key={msg.id ?? `m-${i}`}
              onClick={() => {
                setSelected(msg);
                setReplyText(msg.draft_reply || "");
              }}
              className={cn(
                "flex w-full items-start gap-2 rounded-lg p-3 text-left transition-colors",
                selected?.id === msg.id
                  ? "border border-accent/30 bg-accent/5"
                  : "hover:bg-surface-800"
              )}
            >
              <Icon size={16} style={{ color }} className="mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-surface-200">
                  {msg.sender_name || msg.sender}
                </p>
                <p className="mt-0.5 line-clamp-2 text-xs text-surface-400">{msg.content}</p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Conversation detail */}
      <div className="flex flex-1 flex-col rounded-xl border border-surface-800 bg-surface-900">
        {selected ? (
          <>
            <div className="border-b border-surface-800 px-5 py-4">
              <h3 className="font-medium text-surface-100">
                {selected.sender_name || selected.sender}
              </h3>
              <span className="text-xs capitalize text-surface-500">{selected.platform}</span>
            </div>

            <div className="flex-1 overflow-auto p-5">
              <div className="rounded-lg bg-surface-800 p-4 text-sm text-surface-200">
                {selected.content}
              </div>
              {selected.draft_reply && (
                <div className="mt-3 rounded-lg border border-accent/20 bg-accent/5 p-4 text-sm text-accent-light">
                  <p className="mb-1 text-xs font-medium text-surface-400">AI Draft Reply</p>
                  {selected.draft_reply}
                </div>
              )}
            </div>

            <div className="border-t border-surface-800 p-4">
              <div className="flex gap-2">
                <textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type your reply..."
                  rows={2}
                  className="flex-1 resize-none rounded-lg border border-surface-700 bg-surface-800 px-4 py-2 text-sm text-surface-200 placeholder-surface-500 focus:border-accent focus:outline-none"
                />
                <button
                  onClick={handleReply}
                  disabled={sending || !replyText.trim()}
                  className="flex items-center gap-2 self-end rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-dark disabled:opacity-50"
                >
                  <Send size={16} />
                  Send
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center text-surface-500">
            <MessageCircle size={48} className="mb-4 opacity-30" />
            <p>Select a message to view and reply</p>
          </div>
        )}
      </div>
    </div>
  );
}
