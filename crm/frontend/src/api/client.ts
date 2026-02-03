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

// Handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    // Don't redirect on 422 (validation errors) - let the component handle it
    return Promise.reject(error);
  }
);

export default apiClient;
