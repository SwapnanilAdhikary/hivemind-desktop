import { create } from "zustand";

export interface PlatformMessage {
  id?: number;
  platform: string;
  sender: string;
  sender_name?: string;
  content: string;
  urgency?: string;
  action?: string;
  draft_reply?: string;
  timestamp?: string;
  read?: boolean;
  replied?: boolean;
  type?: string;
  conversation_id?: string;
}

export interface TraceEntry {
  id: number;
  run_id: string;
  agent_name: string;
  node_name: string;
  input_state?: Record<string, unknown>;
  output_state?: Record<string, unknown>;
  timestamp: string;
  duration_ms: number;
}

export interface DecisionEntry {
  id: number;
  trace_id: number;
  node_name: string;
  reasoning: string;
  chosen_action: string;
  alternatives: string[];
  timestamp?: string;
}

export interface PlatformStatusEntry {
  platform: string;
  connected: boolean;
  last_checked?: string;
  error_message?: string;
}

interface AgentState {
  connected: boolean;
  messages: PlatformMessage[];
  traces: TraceEntry[];
  decisions: DecisionEntry[];
  platforms: PlatformStatusEntry[];
  activeTab: string;

  setConnected: (v: boolean) => void;
  addMessage: (msg: PlatformMessage) => void;
  setMessages: (msgs: PlatformMessage[]) => void;
  addTrace: (t: TraceEntry) => void;
  setTraces: (ts: TraceEntry[]) => void;
  addDecision: (d: DecisionEntry) => void;
  setPlatforms: (p: PlatformStatusEntry[]) => void;
  setActiveTab: (tab: string) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  connected: false,
  messages: [],
  traces: [],
  decisions: [],
  platforms: [],
  activeTab: "activity",

  setConnected: (v) => set({ connected: v }),
  addMessage: (msg) =>
    set((s) => ({ messages: [msg, ...s.messages].slice(0, 500) })),
  setMessages: (msgs) => set({ messages: msgs }),
  addTrace: (t) =>
    set((s) => ({ traces: [t, ...s.traces].slice(0, 500) })),
  setTraces: (ts) => set({ traces: ts }),
  addDecision: (d) =>
    set((s) => ({ decisions: [d, ...s.decisions].slice(0, 500) })),
  setPlatforms: (p) => set({ platforms: p }),
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
