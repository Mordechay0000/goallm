/**
 * Rules API endpoints
 */
import apiClient from './client';

export interface Rule {
  id: number;
  profile_id: number;
  domain_pattern: string;
  path_pattern: string | null;
  action: 'allow' | 'block';
  type: '*' | 'image' | 'video';
  include_subdomains: boolean;
  created_at: number;
  updated_at: number;
}

export interface RuleCreate {
  url: string;
  action: 'allow' | 'block';
  type: '*' | 'image' | 'video';
  include_subdomains: boolean;
}

export interface RuleUpdate {
  url?: string;
  action?: 'allow' | 'block';
  type?: '*' | 'image' | 'video';
  include_subdomains?: boolean;
}

export const rulesApi = {
  list: async (profileId: number): Promise<Rule[]> => {
    const response = await apiClient.get<Rule[]>(`/api/profiles/${profileId}/rules`);
    return response.data;
  },

  get: async (id: number): Promise<Rule> => {
    const response = await apiClient.get<Rule>(`/api/rules/${id}`);
    return response.data;
  },

  create: async (profileId: number, data: RuleCreate): Promise<Rule> => {
    const response = await apiClient.post<Rule>(`/api/profiles/${profileId}/rules`, data);
    return response.data;
  },

  update: async (id: number, data: RuleUpdate): Promise<Rule> => {
    const response = await apiClient.put<Rule>(`/api/rules/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/rules/${id}`);
  },
};
