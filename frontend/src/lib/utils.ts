import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const API_BASE = "http://127.0.0.1:8000";
export const WS_URL = "ws://127.0.0.1:8000/ws";

export async function apiFetch<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export const PLATFORM_COLORS: Record<string, string> = {
  gmail: "#EA4335",
  whatsapp: "#25D366",
  instagram: "#E1306C",
  discord: "#5865F2",
};
