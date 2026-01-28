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
  list: async (): Promise<Profile[]> => {
    const response = await apiClient.get<Profile[]>('/api/profiles');
    return response.data;
  },

  get: async (id: number): Promise<Profile> => {
    const response = await apiClient.get<Profile>(`/api/profiles/${id}`);
    return response.data;
  },

  create: async (data: ProfileCreate): Promise<Profile> => {
    const response = await apiClient.post<Profile>('/api/profiles', data);
    return response.data;
  },

  update: async (id: number, data: ProfileUpdate): Promise<Profile> => {
    const response = await apiClient.put<Profile>(`/api/profiles/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/profiles/${id}`);
  },
};
