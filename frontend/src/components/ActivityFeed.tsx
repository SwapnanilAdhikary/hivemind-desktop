import { useAgentStore, type PlatformMessage } from "@/stores/agentStore";
import { cn, PLATFORM_COLORS } from "@/lib/utils";
import { Mail, MessageCircle, Instagram, Hash, Clock } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

const PLATFORM_ICONS: Record<string, React.ElementType> = {
  gmail: Mail,
  whatsapp: MessageCircle,
  instagram: Instagram,
  discord: Hash,
};

function UrgencyBadge({ urgency }: { urgency?: string }) {
  if (!urgency) return null;
  const colors: Record<string, string> = {
    high: "bg-red-500/20 text-red-400",
    medium: "bg-amber-500/20 text-amber-400",
    low: "bg-emerald-500/20 text-emerald-400",
  };
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium uppercase", colors[urgency] ?? colors.medium)}>
      {urgency}
    </span>
  );
}

function MessageCard({ msg }: { msg: PlatformMessage }) {
  const Icon = PLATFORM_ICONS[msg.platform] ?? Mail;
  const color = PLATFORM_COLORS[msg.platform] ?? "#6366f1";
  const timeAgo = msg.timestamp
    ? formatDistanceToNow(new Date(msg.timestamp), { addSuffix: true })
    : "";

  return (
    <div className="group flex gap-3 rounded-xl border border-surface-800 bg-surface-900 p-4 transition-colors hover:border-surface-700">
      <div
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: `${color}20` }}
      >
        <Icon size={20} style={{ color }} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-surface-100">
            {msg.sender_name || msg.sender}
          </span>
          <span className="text-xs capitalize text-surface-500">{msg.platform}</span>
          <UrgencyBadge urgency={msg.urgency} />
          {msg.action && (
            <span className="rounded bg-surface-800 px-1.5 py-0.5 text-[10px] text-surface-400">
              {msg.action}
            </span>
          )}
        </div>
        <p className="mt-1 line-clamp-2 text-sm text-surface-300">{msg.content}</p>
        {msg.draft_reply && (
          <div className="mt-2 rounded-lg border border-accent/20 bg-accent/5 px-3 py-2 text-xs text-accent-light">
            <span className="font-medium">Draft reply:</span> {msg.draft_reply.substring(0, 150)}
          </div>
        )}
        {timeAgo && (
          <div className="mt-1.5 flex items-center gap-1 text-xs text-surface-500">
            <Clock size={12} />
            {timeAgo}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ActivityFeed() {
  const { messages } = useAgentStore();

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-surface-100">Activity Feed</h2>
        <p className="text-sm text-surface-400">
          Real-time messages from all connected platforms
        </p>
      </div>

      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-surface-500">
          <Mail size={48} className="mb-4 opacity-30" />
          <p className="text-lg">No messages yet</p>
          <p className="text-sm">Messages will appear here as they arrive</p>
        </div>
      ) : (
        <div className="space-y-3">
          {messages.map((msg, i) => (
            <MessageCard key={msg.id ?? `msg-${i}`} msg={msg} />
          ))}
        </div>
      )}
    </div>
  );
}
