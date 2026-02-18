import { useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useAgentStore } from "@/stores/agentStore";
import { apiFetch } from "@/lib/utils";
import Sidebar from "./Sidebar";
import ActivityFeed from "./ActivityFeed";
import AgentTraceViewer from "./AgentTraceViewer";
import NodeGraphView from "./NodeGraphView";
import ConversationPanel from "./ConversationPanel";
import ToolRegistryView from "./ToolRegistryView";
import SettingsPanel from "./SettingsPanel";

export default function Dashboard() {
  useWebSocket();
  const { activeTab, setMessages, setTraces, setPlatforms } = useAgentStore();

  useEffect(() => {
    apiFetch("/api/messages?limit=100").then((d: any) => setMessages(d)).catch(() => {});
    apiFetch("/api/traces?limit=100").then((d: any) => setTraces(d)).catch(() => {});
    apiFetch("/api/platforms/status").then((d: any) => setPlatforms(d)).catch(() => {});
  }, [setMessages, setTraces, setPlatforms]);

  const panels: Record<string, React.ReactNode> = {
    activity: <ActivityFeed />,
    traces: <AgentTraceViewer />,
    graph: <NodeGraphView />,
    conversations: <ConversationPanel />,
    tools: <ToolRegistryView />,
    settings: <SettingsPanel />,
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">
        {panels[activeTab] ?? <ActivityFeed />}
      </main>
    </div>
  );
}
