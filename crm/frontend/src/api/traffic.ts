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

  /** Public view by share token (no auth). Anyone with the link can load this. */
  viewByToken: async (token: string): Promise<{ session_id: number; started_at: number; ended_at: number | null; share_token: string; entries: TrafficLogEntry[] }> => {
    const { data } = await apiClient.get<{ session_id: number; started_at: number; ended_at: number | null; share_token: string; entries: TrafficLogEntry[] }>(`/api/traffic/view/${encodeURIComponent(token)}`);
    return data;
  },

  status: async (): Promise<{ recording: boolean; session_id: number | null }> => {
    const { data } = await apiClient.get<{ recording: boolean; session_id: number | null }>('/api/traffic/status');
    return data;
  },

  /** Build the public view URL for a share token (for copying/sharing). */
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
};
