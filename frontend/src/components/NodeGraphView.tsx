import { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { apiFetch, cn } from "@/lib/utils";
import { useAgentStore, type TraceEntry, type DecisionEntry } from "@/stores/agentStore";
import {
  Brain,
  Clock,
  MessageSquare,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  X,
} from "lucide-react";
import { format } from "date-fns";

interface GraphDef {
  nodes: { id: string; label: string; type: string }[];
  edges: { source: string; target: string; label?: string }[];
}

const NODE_TYPE_STYLES: Record<string, { bg: string; border: string }> = {
  process: { bg: "#1e293b", border: "#6366f1" },
  decision: { bg: "#1e293b", border: "#f59e0b" },
  output: { bg: "#1e293b", border: "#10b981" },
  end: { bg: "#1e293b", border: "#64748b" },
};

function layoutNodes(graphDef: GraphDef): { nodes: Node[]; edges: Edge[] } {
  const xSpacing = 250;
  const ySpacing = 120;

  const layers: string[][] = [];
  const placed = new Set<string>();
  const adj = new Map<string, string[]>();

  graphDef.edges.forEach((e) => {
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  });

  const roots = graphDef.nodes.filter(
    (n) => !graphDef.edges.some((e) => e.target === n.id)
  );
  let current = roots.map((r) => r.id);
  while (current.length > 0) {
    const layer = current.filter((id) => !placed.has(id));
    layer.forEach((id) => placed.add(id));
    if (layer.length > 0) layers.push(layer);
    const next: string[] = [];
    layer.forEach((id) => {
      (adj.get(id) || []).forEach((t) => {
        if (!placed.has(t)) next.push(t);
      });
    });
    current = [...new Set(next)];
  }

  graphDef.nodes.forEach((n) => {
    if (!placed.has(n.id)) {
      layers.push([n.id]);
      placed.add(n.id);
    }
  });

  const nodeLookup = new Map(graphDef.nodes.map((n) => [n.id, n]));

  const nodes: Node[] = [];
  layers.forEach((layer, li) => {
    const totalWidth = (layer.length - 1) * xSpacing;
    layer.forEach((id, ni) => {
      const def = nodeLookup.get(id)!;
      const style = NODE_TYPE_STYLES[def.type] || NODE_TYPE_STYLES.process;
      nodes.push({
        id,
        position: { x: ni * xSpacing - totalWidth / 2 + 400, y: li * ySpacing + 50 },
        data: { label: def.label },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        style: {
          background: style.bg,
          border: `2px solid ${style.border}`,
          borderRadius: "12px",
          padding: "12px 20px",
          color: "#e2e8f0",
          fontSize: "13px",
          fontWeight: 500,
          minWidth: "150px",
          textAlign: "center" as const,
        },
      });
    });
  });

  const edges: Edge[] = graphDef.edges.map((e, i) => ({
    id: `e-${i}`,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: true,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#475569" },
    style: { stroke: "#475569", strokeWidth: 2 },
    labelStyle: { fill: "#94a3b8", fontSize: 11, fontWeight: 500 },
    labelBgStyle: { fill: "#0f172a", fillOpacity: 0.8 },
  }));

  return { nodes, edges };
}

function StateField({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || value === "") return null;
  const display = typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  const isLong = display.length > 80;
  return (
    <div className="mb-1.5">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-surface-500">
        {label.replace(/_/g, " ")}
      </span>
      {isLong ? (
        <pre className="mt-0.5 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-surface-950 p-1.5 text-[11px] leading-relaxed text-surface-300">
          {display}
        </pre>
      ) : (
        <p className="mt-0.5 text-[11px] text-surface-200">{display}</p>
      )}
    </div>
  );
}

function TraceDetail({
  trace,
  decisions,
  defaultOpen,
}: {
  trace: TraceEntry;
  decisions: DecisionEntry[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const related = decisions.filter((d) => d.trace_id === trace.id);
  const hasError =
    trace.output_state && typeof trace.output_state === "object" && "error" in trace.output_state;
  const inputEntries = trace.input_state ? Object.entries(trace.input_state) : [];
  const outputEntries = trace.output_state ? Object.entries(trace.output_state) : [];

  return (
    <div
      className={cn(
        "rounded-lg border",
        hasError ? "border-red-800/40 bg-red-950/20" : "border-surface-800 bg-surface-800/50"
      )}
    >
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-surface-800/80"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {hasError ? (
          <AlertTriangle size={12} className="text-red-400" />
        ) : (
          <div className="h-2 w-2 rounded-full bg-accent-light" />
        )}
        <span className="flex-1 font-mono text-surface-300">{trace.run_id}</span>
        <span className="flex items-center gap-1 text-surface-500">
          <Clock size={10} />
          {trace.duration_ms.toFixed(0)}ms
        </span>
        {related.length > 0 && (
          <span className="flex items-center gap-0.5 text-amber-400">
            <Brain size={10} />
            {related.length}
          </span>
        )}
      </button>

      {open && (
        <div className="border-t border-surface-800 px-3 py-2 text-[11px]">
          {/* Input */}
          {inputEntries.length > 0 && (
            <div className="mb-2">
              <div className="mb-1 flex items-center gap-1 text-blue-400">
                <MessageSquare size={10} />
                <span className="text-[10px] font-semibold uppercase">Input</span>
              </div>
              {inputEntries.map(([k, v]) => (
                <StateField key={k} label={k} value={v} />
              ))}
            </div>
          )}

          {/* Output */}
          {outputEntries.length > 0 && (
            <div className="mb-2">
              <div className="mb-1 flex items-center gap-1 text-emerald-400">
                <ArrowRight size={10} />
                <span className="text-[10px] font-semibold uppercase">Output</span>
              </div>
              {outputEntries.map(([k, v]) => (
                <StateField key={k} label={k} value={v} />
              ))}
            </div>
          )}

          {/* Decisions */}
          {related.map((d) => (
            <div
              key={d.id}
              className="mt-1.5 rounded border border-amber-500/20 bg-amber-500/5 px-2 py-1.5"
            >
              <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                {d.chosen_action}
              </span>
              {d.reasoning && (
                <p className="mt-1 text-[11px] leading-relaxed text-surface-300">{d.reasoning}</p>
              )}
              {d.alternatives.length > 0 && (
                <p className="mt-0.5 text-[10px] text-surface-500">
                  Alternatives: {d.alternatives.join(", ")}
                </p>
              )}
            </div>
          ))}

          <p className="mt-1.5 text-[10px] text-surface-600">
            {format(new Date(trace.timestamp), "HH:mm:ss.SSS")}
          </p>
        </div>
      )}
    </div>
  );
}

export default function NodeGraphView() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const traces = useAgentStore((s) => s.traces);
  const decisions = useAgentStore((s) => s.decisions);

  useEffect(() => {
    apiFetch<GraphDef>("/api/graph/definition")
      .then((def) => {
        const { nodes: n, edges: e } = layoutNodes(def);
        setNodes(n);
        setEdges(e);
      })
      .catch(() => {});
  }, []);

  // Highlight active nodes + show execution counts
  useEffect(() => {
    const counts = new Map<string, number>();
    traces.forEach((t) => counts.set(t.node_name, (counts.get(t.node_name) || 0) + 1));

    setNodes((prev) =>
      prev.map((n) => {
        const count = counts.get(n.id) || 0;
        const isActive = count > 0;
        return {
          ...n,
          data: {
            ...n.data,
            label: count > 0 ? `${n.data.label} (${count})` : n.data.label,
          },
          style: {
            ...n.style,
            boxShadow: isActive ? "0 0 20px rgba(99, 102, 241, 0.5)" : "none",
            border: isActive
              ? "2px solid #818cf8"
              : (n.style?.border as string) ?? "2px solid #475569",
          },
        };
      })
    );
  }, [traces]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node.id);
  }, []);

  const nodeTraces = selectedNode
    ? traces.filter((t) => t.node_name === selectedNode)
    : [];

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-surface-100">Decision Graph</h2>
        <p className="text-sm text-surface-400">
          Click any node to inspect its LLM calls, prompts, responses, and decisions
        </p>
      </div>

      <div className="flex gap-4">
        <div className="h-[600px] flex-1 overflow-hidden rounded-xl border border-surface-800 bg-surface-950">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodeClick={onNodeClick}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#1e293b" gap={20} />
            <Controls
              style={{ background: "#1e293b", borderColor: "#334155", borderRadius: "8px" }}
            />
          </ReactFlow>
        </div>

        {selectedNode && (
          <div className="flex w-96 shrink-0 flex-col overflow-hidden rounded-xl border border-surface-800 bg-surface-900">
            <div className="flex items-center justify-between border-b border-surface-800 px-4 py-3">
              <div>
                <h3 className="font-medium text-surface-100">{selectedNode}</h3>
                <p className="text-xs text-surface-500">
                  {nodeTraces.length} execution{nodeTraces.length !== 1 ? "s" : ""}
                  {nodeTraces.length > 0 &&
                    ` -- avg ${(nodeTraces.reduce((s, t) => s + t.duration_ms, 0) / nodeTraces.length).toFixed(0)}ms`}
                </p>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="rounded-lg p-1 text-surface-400 hover:bg-surface-800 hover:text-surface-200"
              >
                <X size={16} />
              </button>
            </div>

            <div className="flex-1 space-y-2 overflow-auto p-3">
              {nodeTraces.length === 0 ? (
                <p className="py-8 text-center text-sm text-surface-500">
                  No executions yet for this node
                </p>
              ) : (
                nodeTraces.slice(0, 20).map((t, i) => (
                  <TraceDetail
                    key={t.id}
                    trace={t}
                    decisions={decisions}
                    defaultOpen={i === 0}
                  />
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
