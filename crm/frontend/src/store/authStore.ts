/**
 * Auth store using Zustand
 */
import { create } from 'zustand';
import type { User, RegisterRequest } from '../api/auth';
import { authApi } from '../api/auth';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (phone: string, password: string) => Promise<void>;
  loginWithPhoneCode: (phone: string, code: string) => Promise<void>;
  loginWithEmailCode: (email: string, code: string) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  init: () => void;
  refreshProfile: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,

  init: async () => {
    const token = localStorage.getItem('access_token');
    const userStr = localStorage.getItem('user');
    if (token && userStr) {
      set({
        token,
        user: JSON.parse(userStr),
        isAuthenticated: true,
      });
      // Refresh user from API to get is_admin and latest data
      try {
        const user = await authApi.getProfile();
        localStorage.setItem('user', JSON.stringify(user));
        set({ user });
      } catch {
        // Ignore - keep stored user
      }
    }
  },

  login: async (phone: string, password: string) => {
    const response = await authApi.login({ phone, password });
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));
    set({
      user: response.user,
      token: response.access_token,
      isAuthenticated: true,
    });
  },

  loginWithPhoneCode: async (phone: string, code: string) => {
    const response = await authApi.verifyPhoneCode(phone, code);
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));
    set({
      user: response.user,
      token: response.access_token,
      isAuthenticated: true,
    });
  },

  loginWithEmailCode: async (email: string, code: string) => {
    const response = await authApi.verifyEmailCode(email, code);
    localStorage.setItem('access_token', response.access_token);
    localStorage.setItem('user', JSON.stringify(response.user));
    set({
      user: response.user,
      token: response.access_token,
      isAuthenticated: true,
    });
  },

  register: async (data: RegisterRequest) => {
    // Validate password before sending
    if (data.password.length < 8) {
      throw new Error('סיסמה חייבת להכיל לפחות 8 תווים');
    }
    if (data.password.length > 128) {
      throw new Error('סיסמה לא יכולה להכיל יותר מ-128 תווים');
    }
    if (!/\d/.test(data.password)) {
      throw new Error('סיסמה חייבת להכיל לפחות ספרה אחת');
    }
    if (!/[a-zA-Zא-ת]/.test(data.password)) {
      throw new Error('סיסמה חייבת להכיל לפחות אות אחת');
    }
    
    await authApi.register(data);
    // Don't login automatically - user needs to login manually
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    set({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  },

  refreshProfile: async () => {
    try {
      const user = await authApi.getProfile();
      localStorage.setItem('user', JSON.stringify(user));
      set({ user });
    } catch (error) {
      console.error('Error refreshing profile:', error);
    }
  },
}));
