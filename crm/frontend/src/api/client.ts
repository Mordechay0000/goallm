/**
 * API client for CRM backend
 */
import axios from 'axios';

// Empty = same origin (Vite proxy forwards /api to backend). Override with VITE_API_URL for direct backend.
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests; omit Content-Type for FormData (browser sets multipart)
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type'];
  }
  return config;
});

// Handle auth errors – redirect to login on 401 only when token expired (not from login attempt).
// When login/verify returns 401, don't redirect – let the form show the error.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const isAuthRequest = String(error.config?.url || '').includes('/auth/');
      if (!isAuthRequest) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        const redirect = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = redirect ? `/login?redirect=${redirect}` : '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
