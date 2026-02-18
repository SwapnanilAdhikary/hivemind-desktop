import { useEffect, useRef, useCallback } from "react";
import { WS_URL } from "@/lib/utils";
import { useAgentStore } from "@/stores/agentStore";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const { addMessage, addTrace, addDecision, setConnected } = useAgentStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const { type, data } = JSON.parse(event.data);
        switch (type) {
          case "new_message":
            addMessage(data);
            if (window.electronAPI) {
              window.electronAPI.showNotification(
                `${data.platform}: ${data.sender_name || data.sender}`,
                data.content?.substring(0, 100) || ""
              );
            }
            break;
          case "trace_update":
            addTrace(data);
            break;
          case "agent_decision":
            addDecision(data);
            break;
          case "reply_sent":
            addMessage({ ...data, type: "reply_sent" });
            break;
          case "tool_created":
            break;
          case "awaiting_approval":
            addMessage({ ...data, type: "awaiting_approval" });
            break;
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [addMessage, addTrace, addDecision, setConnected]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
