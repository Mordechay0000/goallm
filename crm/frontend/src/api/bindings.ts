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

export interface ProxyCredentials {
  username: string | null;
  has_password?: boolean;
  password?: string;
  proxy_host: string;
  proxy_port: number;
}

export const bindingsApi = {
  getProxyCredentials: (): Promise<ProxyCredentials> =>
    apiClient.get('/api/me/proxy-credentials').then((r) => r.data),

  rotateProxyCredentials: (): Promise<ProxyCredentials> =>
    apiClient.post('/api/me/proxy-credentials/rotate').then((r) => r.data),

  list: (): Promise<IpBinding[]> =>
    apiClient.get('/api/me/bindings').then((r) => r.data),

  bindCurrentIp: (): Promise<IpBinding> =>
    apiClient.post('/api/me/bindings').then((r) => r.data),

  getClientIp: (): Promise<{ ip: string }> =>
    apiClient.get('/api/me/client-ip').then((r) => r.data),

  remove: (bindingId: number): Promise<void> =>
    apiClient.delete(`/api/me/bindings/${bindingId}`),
};
