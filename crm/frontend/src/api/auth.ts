/**
 * Auth API endpoints
 */
import apiClient from './client';

const API_BASE = import.meta.env.VITE_API_URL || '';

/** Resolve avatar URL (relative paths get API base). */
export function getAvatarUrl(avatar_url: string | null | undefined): string {
  if (!avatar_url) return '';
  if (avatar_url.startsWith('http://') || avatar_url.startsWith('https://')) return avatar_url;
  return `${API_BASE.replace(/\/$/, '')}${avatar_url.startsWith('/') ? '' : '/'}${avatar_url}`;
}

export interface LoginRequest {
  phone: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone: string;
  avatar?: File | null;
}

export interface User {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  avatar_url?: string;
  created_at: number;
  updated_at: number;
  is_admin?: boolean;
}

export interface UserUpdate {
  email?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  avatar_url?: string | null;
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface SetupStatus {
  needs_setup: boolean;
}

export const authApi = {
  getSetupStatus: async (): Promise<SetupStatus> => {
    const response = await apiClient.get<SetupStatus>('/api/auth/setup-status');
    return response.data;
  },

  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/api/auth/login', data);
    return response.data;
  },

  requestPhoneCode: async (phone: string): Promise<{ sent: boolean; message: string }> => {
    const response = await apiClient.post<{ sent: boolean; message: string }>(
      '/api/auth/request-phone-code',
      { phone }
    );
    return response.data;
  },

  verifyPhoneCode: async (phone: string, code: string): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/api/auth/verify-phone-code', {
      phone,
      code,
    });
    return response.data;
  },

  requestEmailCode: async (email: string): Promise<{ sent: boolean; message: string }> => {
    const response = await apiClient.post<{ sent: boolean; message: string }>(
      '/api/auth/request-email-code',
      { email }
    );
    return response.data;
  },

  verifyEmailCode: async (email: string, code: string): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/api/auth/verify-email-code', {
      email,
      code,
    });
    return response.data;
  },

  register: async (data: RegisterRequest): Promise<User> => {
    const form = new FormData();
    form.append('email', data.email);
    form.append('password', data.password);
    form.append('first_name', data.first_name);
    form.append('last_name', data.last_name);
    form.append('phone', data.phone);
    if (data.avatar) form.append('avatar', data.avatar);
    const response = await apiClient.post<User>('/api/auth/register', form);
    return response.data;
  },

  uploadAvatar: async (file: File): Promise<User> => {
    const form = new FormData();
    form.append('file', file);
    const response = await apiClient.post<User>('/api/user/me/avatar', form);
    return response.data;
  },

  getMyLockedSettings: async (): Promise<string[]> => {
    const response = await apiClient.get<{ locked_settings: string[] }>('/api/user/me/locked-settings');
    return response.data.locked_settings;
  },

  getProfile: async (): Promise<User> => {
    const response = await apiClient.get<User>('/api/user/me');
    return response.data;
  },

  updateProfile: async (data: UserUpdate): Promise<User> => {
    const response = await apiClient.put<User>('/api/user/me', data);
    return response.data;
  },

  changePassword: async (data: PasswordChange): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post('/api/user/me/change-password', {
      current_password: data.current_password,
      new_password: data.new_password,
    });
    return response.data;
  },
};
