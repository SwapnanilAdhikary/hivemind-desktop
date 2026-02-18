import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/utils";
import { Wrench, Trash2, ToggleLeft, ToggleRight, Play, Plus, Code } from "lucide-react";

interface ToolEntry {
  id: number;
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  usage_count: number;
  enabled: boolean;
  created_at: string | null;
}

export default function ToolRegistryView() {
  const [tools, setTools] = useState<ToolEntry[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [showAiCreate, setShowAiCreate] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [newTool, setNewTool] = useState({ name: "", description: "", source_code: "" });
  const [selectedTool, setSelectedTool] = useState<ToolEntry | null>(null);

  const loadTools = () => {
    apiFetch<ToolEntry[]>("/api/tools").then(setTools).catch(() => {});
  };

  useEffect(() => {
    loadTools();
  }, []);

  const handleCreate = async () => {
    if (!newTool.name || !newTool.source_code) return;
    await apiFetch("/api/tools", {
      method: "POST",
      body: JSON.stringify(newTool),
    });
    setNewTool({ name: "", description: "", source_code: "" });
    setShowCreate(false);
    loadTools();
  };

  const handleAiCreate = async () => {
    if (!aiPrompt.trim()) return;
    setAiLoading(true);
    try {
      await apiFetch("/api/tools/create", {
        method: "POST",
        body: JSON.stringify({ task_description: aiPrompt }),
      });
      setAiPrompt("");
      setShowAiCreate(false);
      loadTools();
    } catch {
      // handle error
    }
    setAiLoading(false);
  };

  const handleDelete = async (name: string) => {
    await apiFetch(`/api/tools/${name}`, { method: "DELETE" });
    loadTools();
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    await apiFetch(`/api/tools/${name}/toggle?enabled=${!enabled}`, { method: "PATCH" });
    loadTools();
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-surface-100">Tool Registry</h2>
          <p className="text-sm text-surface-400">
            Manage built-in and AI-generated tools
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowAiCreate(!showAiCreate); setShowCreate(false); }}
            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            <Wrench size={16} />
            AI Create
          </button>
          <button
            onClick={() => { setShowCreate(!showCreate); setShowAiCreate(false); }}
            className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark"
          >
            <Plus size={16} />
            Manual
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-xl border border-surface-700 bg-surface-900 p-4 space-y-3">
          <input
            type="text"
            placeholder="Tool name (must match function name)"
            value={newTool.name}
            onChange={(e) => setNewTool((p) => ({ ...p, name: e.target.value }))}
            className="w-full rounded-lg border border-surface-700 bg-surface-800 px-4 py-2 text-sm text-surface-200 placeholder-surface-500 focus:border-accent focus:outline-none"
          />
          <input
            type="text"
            placeholder="Description"
            value={newTool.description}
            onChange={(e) => setNewTool((p) => ({ ...p, description: e.target.value }))}
            className="w-full rounded-lg border border-surface-700 bg-surface-800 px-4 py-2 text-sm text-surface-200 placeholder-surface-500 focus:border-accent focus:outline-none"
          />
          <textarea
            placeholder="Python source code (define a function matching the tool name)"
            value={newTool.source_code}
            onChange={(e) => setNewTool((p) => ({ ...p, source_code: e.target.value }))}
            rows={6}
            className="w-full resize-none rounded-lg border border-surface-700 bg-surface-800 px-4 py-2 font-mono text-sm text-surface-200 placeholder-surface-500 focus:border-accent focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-dark"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="rounded-lg bg-surface-800 px-4 py-2 text-sm text-surface-300 hover:bg-surface-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {showAiCreate && (
        <div className="mb-6 rounded-xl border border-emerald-800 bg-surface-900 p-4 space-y-3">
          <p className="text-sm text-surface-300">
            Describe what you need the tool to do. The AI will generate, validate, and register it.
          </p>
          <textarea
            placeholder="e.g., A function that converts CSV text to a list of dictionaries"
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            rows={3}
            className="w-full resize-none rounded-lg border border-surface-700 bg-surface-800 px-4 py-2 text-sm text-surface-200 placeholder-surface-500 focus:border-emerald-500 focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              onClick={handleAiCreate}
              disabled={aiLoading || !aiPrompt.trim()}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {aiLoading ? "Creating..." : "Generate Tool"}
            </button>
            <button
              onClick={() => setShowAiCreate(false)}
              className="rounded-lg bg-surface-800 px-4 py-2 text-sm text-surface-300 hover:bg-surface-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {tools.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-surface-500">
          <Wrench size={48} className="mb-4 opacity-30" />
          <p className="text-lg">No tools registered</p>
          <p className="text-sm">Tools created by the AI agent will appear here</p>
        </div>
      ) : (
        <div className="space-y-2">
          {tools.map((tool) => (
            <div
              key={tool.id}
              className="flex items-center gap-4 rounded-xl border border-surface-800 bg-surface-900 p-4"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10">
                <Code size={20} className="text-accent-light" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-surface-100">{tool.name}</span>
                  <span className="rounded bg-surface-800 px-1.5 py-0.5 text-[10px] text-surface-400">
                    used {tool.usage_count}x
                  </span>
                  {!tool.enabled && (
                    <span className="rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] text-red-400">
                      disabled
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-sm text-surface-400">{tool.description}</p>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleToggle(tool.name, tool.enabled)}
                  className="rounded-lg p-2 text-surface-400 hover:bg-surface-800 hover:text-surface-200"
                  title={tool.enabled ? "Disable" : "Enable"}
                >
                  {tool.enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                </button>
                <button
                  onClick={() => handleDelete(tool.name)}
                  className="rounded-lg p-2 text-surface-400 hover:bg-red-500/10 hover:text-red-400"
                  title="Delete"
                >
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
