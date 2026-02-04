/**
 * IP bindings API – שיוך כתובת IP לחשבון
 */
import apiClient from './client';

export interface IpBinding {
  id: number;
  ip: string;
  created_at: number;
  last_used_at?: number | null;
}

export const bindingsApi = {
  list: (): Promise<IpBinding[]> =>
    apiClient.get('/api/me/bindings').then((r) => r.data),

  bindCurrentIp: (): Promise<IpBinding> =>
    apiClient.post('/api/me/bindings').then((r) => r.data),

  getClientIp: (): Promise<{ ip: string }> =>
    apiClient.get('/api/me/client-ip').then((r) => r.data),

  remove: (bindingId: number): Promise<void> =>
    apiClient.delete(`/api/me/bindings/${bindingId}`),
};
