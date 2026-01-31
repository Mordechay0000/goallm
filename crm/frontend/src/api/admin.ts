/**
 * Admin API (admin only)
 */
import apiClient from './client';

export interface AdminUser {
  id: number;
  phone: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  is_admin: boolean;
  created_at: number;
}

export const adminApi = {
  listUsers: async (params?: { sort_by?: string; sort_order?: string; page?: number; page_size?: number; search?: string }): Promise<{ users: AdminUser[]; total: number }> => {
    const response = await apiClient.get<{ users: AdminUser[]; total: number }>('/api/admin/users', { params });
    return response.data;
  },

  setUserAdmin: async (userId: number, isAdmin: boolean): Promise<void> => {
    await apiClient.put(`/api/admin/users/${userId}/admin`, { is_admin: isAdmin });
  },

  deleteUser: async (userId: number): Promise<void> => {
    await apiClient.delete(`/api/admin/users/${userId}`);
  },

  getLockedSettings: async (userId: number): Promise<string[]> => {
    const response = await apiClient.get<{ locked_settings: string[] }>(`/api/admin/users/${userId}/locked-settings`);
    return response.data.locked_settings;
  },

  addLockedSetting: async (userId: number, settingKey: string): Promise<string[]> => {
    const response = await apiClient.post<{ locked_settings: string[] }>(`/api/admin/users/${userId}/locked-settings`, { setting_key: settingKey });
    return response.data.locked_settings;
  },

  removeLockedSetting: async (userId: number, settingKey: string): Promise<string[]> => {
    const response = await apiClient.delete<{ locked_settings: string[] }>(`/api/admin/users/${userId}/locked-settings/${settingKey}`);
    return response.data.locked_settings;
  },

  listAllProfiles: async (): Promise<{ id: number; user_id: number; name: string; mode: string; user_phone?: string }[]> => {
    const response = await apiClient.get<{ profiles: { id: number; user_id: number; name: string; mode: string; user_phone?: string }[] }>('/api/admin/all-profiles');
    return response.data.profiles;
  },

  // Global rules (רשימה גלובלית – admin only)
  listGlobalRules: async (): Promise<GlobalRule[]> => {
    const response = await apiClient.get<GlobalRule[]>('/api/admin/global-rules');
    return response.data;
  },
  createGlobalRule: async (data: GlobalRuleCreate): Promise<GlobalRule> => {
    const response = await apiClient.post<GlobalRule>('/api/admin/global-rules', data);
    return response.data;
  },
  getGlobalRule: async (ruleId: number): Promise<GlobalRule> => {
    const response = await apiClient.get<GlobalRule>(`/api/admin/global-rules/${ruleId}`);
    return response.data;
  },
  updateGlobalRule: async (ruleId: number, data: GlobalRuleUpdate): Promise<GlobalRule> => {
    const response = await apiClient.put<GlobalRule>(`/api/admin/global-rules/${ruleId}`, data);
    return response.data;
  },
  deleteGlobalRule: async (ruleId: number): Promise<void> => {
    await apiClient.delete(`/api/admin/global-rules/${ruleId}`);
  },
};

export interface GlobalRule {
  id: number;
  domain_pattern: string;
  path_pattern?: string;
  action: string;
  type: string;
  include_subdomains: boolean;
  tags?: string[];
  created_at: number;
  updated_at: number;
  display_url?: string;
}

export interface GlobalRuleCreate {
  url: string;
  action?: string;
  type?: string;
  include_subdomains?: boolean;
  tags?: string[];
}

export interface GlobalRuleUpdate {
  url?: string;
  action?: string;
  type?: string;
  include_subdomains?: boolean;
  tags?: string[];
}
