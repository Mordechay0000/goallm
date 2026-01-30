/**
 * Profiles API endpoints
 */
import apiClient from './client';

export interface Profile {
  id: number;
  user_id: number;
  name: string;
  mode: 'whitelist' | 'blacklist';
  is_default: boolean;
  created_at: number;
  updated_at: number;
}

export interface ProfileCreate {
  name: string;
  mode: 'whitelist' | 'blacklist';
}

export interface ProfileUpdate {
  name?: string;
  mode?: 'whitelist' | 'blacklist';
}

export const profilesApi = {
  list: async (managedUserId?: number): Promise<Profile[]> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.get<Profile[]>('/api/profiles', { params });
    return response.data;
  },

  get: async (id: number, managedUserId?: number): Promise<Profile> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.get<Profile>(`/api/profiles/${id}`, { params });
    return response.data;
  },

  create: async (data: ProfileCreate, managedUserId?: number): Promise<Profile> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.post<Profile>('/api/profiles', data, { params });
    return response.data;
  },

  update: async (id: number, data: ProfileUpdate, managedUserId?: number): Promise<Profile> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.put<Profile>(`/api/profiles/${id}`, data, { params });
    return response.data;
  },

  delete: async (id: number, managedUserId?: number): Promise<void> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    await apiClient.delete(`/api/profiles/${id}`, { params });
  },
};
