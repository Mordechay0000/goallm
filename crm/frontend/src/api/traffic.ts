/**
 * API for traffic recording: start, stop, status, log.
 * Recording is only while the page is open; closing the tab stops it.
 */
import apiClient from './client';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export interface TrafficSession {
  id: number;
  user_id: number;
  started_at: number;
  ended_at: number | null;
}

export interface TrafficLogEntry {
  id: number;
  session_id: number;
  url: string;
  protocol: string;
  status: string;
  time_sec: number;
  content_type: string;
  created_at: number;
}

/** Call when page is closing so recording stops. Uses fetch keepalive so the request can complete after the tab closes. */
export function stopTrafficOnPageUnload(): void {
  const token = localStorage.getItem('access_token');
  if (!token) return;
  const url = `${API_BASE_URL}/api/traffic/stop`;
  try {
    fetch(url, {
      method: 'POST',
      keepalive: true,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
  } catch {
    // ignore
  }
}

export const trafficApi = {
  start: async (): Promise<{ session_id: number; message: string }> => {
    const { data } = await apiClient.post<{ session_id: number; message: string }>('/api/traffic/start');
    return data;
  },

  stop: async (): Promise<{ session_id: number; share_token: string; message: string }> => {
    const { data } = await apiClient.post<{ session_id: number; share_token: string; message: string }>('/api/traffic/stop');
    return data;
  },

  /** View recording by share token. Requires login; view is logged for security audit. */
  viewByToken: async (token: string): Promise<{ session_id: number; started_at: number; ended_at: number | null; share_token: string; entries: TrafficLogEntry[] }> => {
    const { data } = await apiClient.get<{ session_id: number; started_at: number; ended_at: number | null; share_token: string; entries: TrafficLogEntry[] }>(`/api/traffic/view/${encodeURIComponent(token)}`);
    return data;
  },

  status: async (): Promise<{ recording: boolean; session_id: number | null }> => {
    const { data } = await apiClient.get<{ recording: boolean; session_id: number | null }>('/api/traffic/status');
    return data;
  },

  /** Build the view URL for a share token (for copying/sharing). Opening it requires login. */
  getViewUrl: (token: string): string => {
    const base = typeof window !== 'undefined' ? window.location.origin : '';
    return `${base}/tools/traffic/view/${encodeURIComponent(token)}`;
  },

  log: async (sessionId: number): Promise<{ session_id: number; entries: TrafficLogEntry[] }> => {
    const { data } = await apiClient.get<{ session_id: number; entries: TrafficLogEntry[] }>('/api/traffic/log', {
      params: { session_id: sessionId },
    });
    return data;
  },

  /**
   * Connect WebSocket for live traffic log during recording.
   * Calls onEntries(newEntries) when new rows arrive. Returns close() to disconnect.
   */
  connectTrafficLive: (
    onEntries: (entries: TrafficLogEntry[]) => void,
    onError?: (message: string) => void
  ): (() => void) => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      onError?.('לא מחובר');
      return () => {};
    }
    const wsBase = API_BASE_URL
      ? API_BASE_URL.replace(/^http/, 'ws')
      : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
    const url = `${wsBase}/ws/traffic?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string);
        if (msg.type === 'traffic_log' && Array.isArray(msg.entries)) {
          onEntries(msg.entries);
        }
        if (msg.type === 'no_session' && msg.message) {
          onError?.(msg.message);
        }
      } catch {
        // ignore
      }
    };
    ws.onerror = () => onError?.('שגיאת חיבור');
    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  },
};
