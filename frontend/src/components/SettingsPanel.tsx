import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/utils";
import { Server, Cpu, Key, RefreshCw } from "lucide-react";

interface HealthData {
  status: string;
  ollama_available: boolean;
  openai_configured: boolean;
  anthropic_configured: boolean;
  websocket_clients: number;
}

interface ModelsData {
  ollama: string[];
  openai: string[];
  anthropic: string[];
}

export default function SettingsPanel() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [models, setModels] = useState<ModelsData | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const [h, m] = await Promise.all([
        apiFetch<HealthData>("/api/health"),
        apiFetch<ModelsData>("/api/llm/models"),
      ]);
      setHealth(h);
      setModels(m);
    } catch {
      // handle error
    }
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-surface-100">Settings</h2>
          <p className="text-sm text-surface-400">System status and configuration</p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg bg-surface-800 px-4 py-2 text-sm text-surface-300 hover:bg-surface-700"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* System Status */}
      <section className="mb-6 rounded-xl border border-surface-800 bg-surface-900 p-5">
        <h3 className="mb-4 flex items-center gap-2 font-medium text-surface-100">
          <Server size={18} />
          System Status
        </h3>
        {health ? (
          <div className="grid grid-cols-2 gap-4">
            <StatusItem label="Backend" ok={health.status === "ok"} />
            <StatusItem label="Ollama" ok={health.ollama_available} />
            <StatusItem label="OpenAI API" ok={health.openai_configured} />
            <StatusItem label="Anthropic API" ok={health.anthropic_configured} />
            <div className="col-span-2 text-sm text-surface-400">
              WebSocket clients: {health.websocket_clients}
            </div>
          </div>
        ) : (
          <p className="text-sm text-surface-500">Loading...</p>
        )}
      </section>

      {/* Available Models */}
      <section className="rounded-xl border border-surface-800 bg-surface-900 p-5">
        <h3 className="mb-4 flex items-center gap-2 font-medium text-surface-100">
          <Cpu size={18} />
          Available Models
        </h3>
        {models ? (
          <div className="space-y-4">
            <ModelGroup label="Ollama (Local)" models={models.ollama} />
            <ModelGroup label="OpenAI" models={models.openai} />
            <ModelGroup label="Anthropic" models={models.anthropic} />
          </div>
        ) : (
          <p className="text-sm text-surface-500">Loading...</p>
        )}
      </section>
    </div>
  );
}

function StatusItem({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`h-2.5 w-2.5 rounded-full ${ok ? "bg-emerald-400" : "bg-surface-600"}`} />
      <span className="text-surface-300">{label}</span>
      <span className={`text-xs ${ok ? "text-emerald-400" : "text-surface-500"}`}>
        {ok ? "Active" : "Inactive"}
      </span>
    </div>
  );
}

function ModelGroup({ label, models }: { label: string; models: string[] }) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-surface-500">
        {label}
      </p>
      {models.length === 0 ? (
        <p className="text-sm text-surface-600">None available</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {models.map((m) => (
            <span
              key={m}
              className="rounded-lg bg-surface-800 px-3 py-1 text-xs text-surface-300"
            >
              {m}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
