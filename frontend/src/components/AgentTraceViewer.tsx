import { useAgentStore, type TraceEntry, type DecisionEntry } from "@/stores/agentStore";
import { cn } from "@/lib/utils";
import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Zap,
  Brain,
  Clock,
  MessageSquare,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";
import { format } from "date-fns";

function StateField({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === "") return null;
  const display = typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  const isLong = display.length > 120;

  return (
    <div className="mb-2">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-surface-500">
        {label.replace(/_/g, " ")}
      </span>
      {isLong ? (
        <pre className="mt-0.5 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-surface-950 p-2 text-xs leading-relaxed text-surface-300">
          {display}
        </pre>
      ) : (
        <p className="mt-0.5 text-xs text-surface-200">{display}</p>
      )}
    </div>
  );
}

function TraceNode({ trace, decisions }: { trace: TraceEntry; decisions: DecisionEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  const relatedDecisions = decisions.filter((d) => d.trace_id === trace.id);

  const hasError =
    trace.output_state && typeof trace.output_state === "object" && "error" in trace.output_state;
  const inputEntries = trace.input_state ? Object.entries(trace.input_state) : [];
  const outputEntries = trace.output_state ? Object.entries(trace.output_state) : [];

  return (
    <div
      className={cn(
        "rounded-lg border bg-surface-900",
        hasError ? "border-red-800/50" : "border-surface-800"
      )}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-800/50"
      >
        {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {hasError ? (
          <AlertTriangle size={16} className="text-red-400" />
        ) : (
          <Zap size={16} className="text-accent-light" />
        )}
        <div className="flex-1">
          <span className="font-medium text-surface-100">{trace.node_name}</span>
          <span className="ml-2 text-xs text-surface-500">{trace.agent_name}</span>
          {relatedDecisions.length > 0 && (
            <span className="ml-2 inline-flex items-center gap-1 rounded bg-accent/10 px-1.5 py-0.5 text-[10px] text-accent-light">
              <Brain size={10} />
              {relatedDecisions.length} decision{relatedDecisions.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-surface-400">
          <Clock size={12} />
          {trace.duration_ms.toFixed(0)}ms
        </div>
        <span className="rounded bg-surface-800 px-2 py-0.5 text-[10px] text-surface-400">
          {format(new Date(trace.timestamp), "HH:mm:ss")}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-surface-800 px-4 py-3">
          <div className="grid grid-cols-2 gap-6">
            {/* Input - what was sent to the LLM */}
            <div>
              <div className="mb-2 flex items-center gap-2">
                <MessageSquare size={14} className="text-blue-400" />
                <p className="text-xs font-semibold uppercase tracking-wider text-blue-400">
                  Input (sent to LLM)
                </p>
              </div>
              {inputEntries.length === 0 ? (
                <p className="text-xs italic text-surface-600">No input recorded</p>
              ) : (
                inputEntries.map(([key, val]) => (
                  <StateField key={key} label={key} value={val} />
                ))
              )}
            </div>

            {/* Output - what the LLM returned */}
            <div>
              <div className="mb-2 flex items-center gap-2">
                <ArrowRight size={14} className="text-emerald-400" />
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  Output (LLM response)
                </p>
              </div>
              {outputEntries.length === 0 ? (
                <p className="text-xs italic text-surface-600">No output recorded</p>
              ) : (
                outputEntries.map(([key, val]) => (
                  <StateField key={key} label={key} value={val} />
                ))
              )}
            </div>
          </div>

          {/* Decisions */}
          {relatedDecisions.length > 0 && (
            <div className="mt-4 space-y-2">
              <div className="flex items-center gap-2">
                <Brain size={14} className="text-amber-400" />
                <p className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                  Decisions
                </p>
              </div>
              {relatedDecisions.map((d) => (
                <div
                  key={d.id}
                  className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-300">
                      {d.chosen_action}
                    </span>
                  </div>
                  {d.reasoning && (
                    <p className="mt-1.5 text-xs leading-relaxed text-surface-300">{d.reasoning}</p>
                  )}
                  {d.alternatives.length > 0 && (
                    <p className="mt-1 text-[10px] text-surface-500">
                      Other options considered: {d.alternatives.join(", ")}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Run ID */}
          <div className="mt-3 text-[10px] text-surface-600">
            Run ID: {trace.run_id}
          </div>
        </div>
      )}
    </div>
  );
}

export default function AgentTraceViewer() {
  const { traces, decisions } = useAgentStore();
  const [filter, setFilter] = useState("");

  const filtered = traces.filter(
    (t) =>
      !filter ||
      t.node_name.toLowerCase().includes(filter.toLowerCase()) ||
      t.agent_name.toLowerCase().includes(filter.toLowerCase()) ||
      t.run_id.toLowerCase().includes(filter.toLowerCase())
  );

  // Group by run_id
  const runs = new Map<string, TraceEntry[]>();
  for (const t of filtered) {
    if (!runs.has(t.run_id)) runs.set(t.run_id, []);
    runs.get(t.run_id)!.push(t);
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-surface-100">Agent Traces</h2>
        <p className="text-sm text-surface-400">
          Full transparency into every LLM call, prompt, response, and decision
        </p>
      </div>

      <input
        type="text"
        placeholder="Filter by node name, agent, or run ID..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4 w-full rounded-lg border border-surface-700 bg-surface-800 px-4 py-2 text-sm text-surface-200 placeholder-surface-500 focus:border-accent focus:outline-none"
      />

      {runs.size === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-surface-500">
          <Zap size={48} className="mb-4 opacity-30" />
          <p className="text-lg">No traces yet</p>
          <p className="text-sm">Agent execution traces will appear here</p>
        </div>
      ) : (
        <div className="space-y-4">
          {[...runs.entries()].map(([runId, runTraces]) => (
            <div key={runId}>
              <div className="mb-1.5 flex items-center gap-2 text-xs text-surface-500">
                <span className="rounded bg-surface-800 px-2 py-0.5 font-mono">
                  Run {runId}
                </span>
                <span>{runTraces.length} step{runTraces.length > 1 ? "s" : ""}</span>
                <span>
                  {runTraces.reduce((sum, t) => sum + t.duration_ms, 0).toFixed(0)}ms total
                </span>
              </div>
              <div className="space-y-1.5">
                {runTraces.map((t) => (
                  <TraceNode key={t.id} trace={t} decisions={decisions} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
