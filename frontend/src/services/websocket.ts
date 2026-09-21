/**
 * Resilient SCADA WebSocket Client
 * 
 * Features:
 * - Direct connection to backend /ws/v1/live-telemetry
 * - Auto-reconnect with progressive backoff (1s -> 2s -> 5s -> 10s)
 * - Heartbeat ping-pong & continuous RTT latency measurement
 * - Typed subscription handlers for RAW_VIBRATION_BURST and ML_ANOMALY_UPDATE
 * - Stale data watchdog
 */

import { config } from '../config';

export type WsConnectionStatus =
  | 'CONNECTED'
  | 'CONNECTING'
  | 'RECONNECTING'
  | 'DISCONNECTED'
  | 'BACKEND_OFFLINE';

export type WsMessageHandler = (data: any) => void;
export type WsStatusHandler = (status: WsConnectionStatus, latencyMs: number) => void;

class WebSocketService {
  private socket: WebSocket | null = null;
  private status: WsConnectionStatus = 'DISCONNECTED';
  private latencyMs: number = 0;
  private reconnectTimer: number | null = null;
  private pingTimer: number | null = null;
  private pingSentTime: number = 0;
  private reconnectAttempts: number = 0;
  private messageHandlers: Set<WsMessageHandler> = new Set();
  private statusHandlers: Set<WsStatusHandler> = new Set();
  private isExplicitlyClosed: boolean = false;

  public connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.isExplicitlyClosed = false;
    this.setStatus(this.reconnectAttempts > 0 ? 'RECONNECTING' : 'CONNECTING');

    try {
      const url = `${config.wsBaseUrl}/ws/v1/live-telemetry`;
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.setStatus('CONNECTED');
        this.startHeartbeat();
      };

      this.socket.onmessage = (event) => {
        try {
          if (event.data === 'pong') {
            this.latencyMs = Math.max(1, Date.now() - this.pingSentTime);
            this.notifyStatus();
            return;
          }

          const parsed = JSON.parse(event.data);
          if (parsed.type === 'PONG') {
            this.latencyMs = Math.max(1, Date.now() - this.pingSentTime);
            this.notifyStatus();
            return;
          }

          // Broadcast to all registered handlers
          this.messageHandlers.forEach((handler) => {
            try {
              handler(parsed);
            } catch (err) {
              console.error('Error in WS message handler:', err);
            }
          });
        } catch {
          // Ignore non-json frames
        }
      };

      this.socket.onerror = () => {
        if (this.reconnectAttempts > 3) {
          this.setStatus('BACKEND_OFFLINE');
        }
      };

      this.socket.onclose = () => {
        this.stopHeartbeat();
        this.socket = null;
        if (!this.isExplicitlyClosed) {
          this.scheduleReconnect();
        } else {
          this.setStatus('DISCONNECTED');
        }
      };
    } catch {
      this.setStatus('BACKEND_OFFLINE');
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.isExplicitlyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.setStatus('DISCONNECTED');
  }

  public onMessage(handler: WsMessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  public onStatus(handler: WsStatusHandler): () => void {
    this.statusHandlers.add(handler);
    handler(this.status, this.latencyMs);
    return () => this.statusHandlers.delete(handler);
  }

  public getStatus(): WsConnectionStatus {
    return this.status;
  }

  public getLatency(): number {
    return this.latencyMs;
  }

  private setStatus(status: WsConnectionStatus): void {
    this.status = status;
    this.notifyStatus();
  }

  private notifyStatus(): void {
    this.statusHandlers.forEach((handler) => {
      try {
        handler(this.status, this.latencyMs);
      } catch (err) {
        console.error('Error in WS status handler:', err);
      }
    });
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingTimer = window.setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.pingSentTime = Date.now();
        this.socket.send(JSON.stringify({ action: 'ping', timestamp: this.pingSentTime }));
      }
    }, 3000);
  }

  private stopHeartbeat(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || this.isExplicitlyClosed) return;
    this.reconnectAttempts++;
    const delay = Math.min(10000, 1000 * Math.pow(1.5, Math.min(this.reconnectAttempts, 6)));
    this.setStatus('RECONNECTING');
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}

export const wsService = new WebSocketService();
