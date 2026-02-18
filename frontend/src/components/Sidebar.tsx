import { cn } from "@/lib/utils";
import { useAgentStore } from "@/stores/agentStore";
import {
  Activity,
  BarChart3,
  GitBranch,
  MessageSquare,
  Wrench,
  Settings,
  Wifi,
  WifiOff,
} from "lucide-react";

const NAV_ITEMS = [
  { id: "activity", label: "Activity", icon: Activity },
  { id: "traces", label: "Traces", icon: BarChart3 },
  { id: "graph", label: "Graph", icon: GitBranch },
  { id: "conversations", label: "Messages", icon: MessageSquare },
  { id: "tools", label: "Tools", icon: Wrench },
  { id: "settings", label: "Settings", icon: Settings },
] as const;

export default function Sidebar() {
  const { activeTab, setActiveTab, connected, platforms } = useAgentStore();

  return (
    <aside className="flex w-64 flex-col border-r border-surface-800 bg-surface-900">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-surface-800 px-5 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent font-bold text-white">
          A
        </div>
        <div>
          <h1 className="text-sm font-semibold text-surface-100">Agent Platform</h1>
          <div className="flex items-center gap-1.5 text-xs text-surface-400">
            {connected ? (
              <>
                <Wifi size={12} className="text-emerald-400" />
                Connected
              </>
            ) : (
              <>
                <WifiOff size={12} className="text-red-400" />
                Disconnected
              </>
            )}
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              activeTab === id
                ? "bg-accent/10 text-accent-light"
                : "text-surface-400 hover:bg-surface-800 hover:text-surface-200"
            )}
          >
            <Icon size={18} />
            {label}
          </button>
        ))}
      </nav>

      {/* Platform Status */}
      <div className="border-t border-surface-800 px-4 py-3">
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-surface-500">
          Platforms
        </p>
        <div className="space-y-1.5">
          {(platforms.length > 0 ? platforms : [
            { platform: "gmail", connected: false },
            { platform: "whatsapp", connected: false },
            { platform: "instagram", connected: false },
            { platform: "discord", connected: false },
          ]).map((p) => (
            <div key={p.platform} className="flex items-center gap-2 text-xs">
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  p.connected ? "bg-emerald-400" : "bg-surface-600"
                )}
              />
              <span className="capitalize text-surface-300">{p.platform}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
