// WebSocket client. The ONLY file that manages WS connections.

import { API_BASE } from "./api";
import type { RunStatus } from "../types";

const WS_BASE = API_BASE.replace(/^http/, "ws");

export interface AgentStatusEvent {
  status: RunStatus | string;
  message: string;
}

export interface AgentErrorEvent {
  message: string;
}

export interface AgentWSCallbacks {
  onStatus?: (data: AgentStatusEvent) => void;
  onComplete?: (data: unknown) => void;
  onError?: (data: AgentErrorEvent) => void;
}

interface WSMessage {
  event: "status" | "complete" | "error";
  data: unknown;
}

export class AgentWS {
  private ws: WebSocket | null = null;
  private connected = false;

  constructor(
    private readonly runId: string,
    private readonly callbacks: AgentWSCallbacks
  ) {
    this.connect();
  }

  private connect(): void {
    const ws = new WebSocket(`${WS_BASE}/ws/${this.runId}`);
    this.ws = ws;

    ws.onopen = () => {
      this.connected = true;
    };
    ws.onclose = () => {
      this.connected = false;
    };
    ws.onerror = () => {
      this.connected = false;
    };
    ws.onmessage = (event: MessageEvent) => {
      let msg: WSMessage;
      try {
        msg = JSON.parse(event.data as string) as WSMessage;
      } catch {
        return;
      }
      switch (msg.event) {
        case "status":
          this.callbacks.onStatus?.(msg.data as AgentStatusEvent);
          break;
        case "complete":
          this.callbacks.onComplete?.(msg.data);
          break;
        case "error":
          this.callbacks.onError?.(msg.data as AgentErrorEvent);
          break;
      }
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
    this.connected = false;
  }

  get isConnected(): boolean {
    return this.connected;
  }
}
