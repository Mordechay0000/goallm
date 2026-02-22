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
  resolveGlobalRule: async (url: string): Promise<{ rule: GlobalRule | null }> => {
    const response = await apiClient.get<{ rule: GlobalRule | null }>('/api/admin/global-rules/resolve', {
      params: { url: url.trim() },
    });
    return response.data;
  },
  /** Update existing global rule (by domain+path) to block. Admin only. */
  surfUpdateRuleToBlock: async (ruleDomain: string, rulePath: string): Promise<{ success: boolean; rule: GlobalRule }> => {
    const response = await apiClient.post<{ success: boolean; rule: GlobalRule }>('/api/admin/surf-update-rule-to-block', {
      rule_domain: ruleDomain,
      rule_path: rulePath || '/',
    });
    return response.data;
  },

  // Allowed file downloads (רשימת קבצים מאושרים – אדמין)
  listAllowedFileDownloads: async (): Promise<AllowedFileItem[]> => {
    const response = await apiClient.get<{ items: AllowedFileItem[] }>('/api/admin/allowed-file-downloads');
    return response.data.items;
  },
  addAllowedFileDownload: async (url: string): Promise<{ url: string }> => {
    const response = await apiClient.post<{ url: string }>('/api/admin/allowed-file-downloads', { url: url.trim() });
    return response.data;
  },
  removeAllowedFileDownload: async (url: string): Promise<void> => {
    await apiClient.delete('/api/admin/allowed-file-downloads', { data: { url: url.trim() } });
  },

  // Filter switches (הפעלה/כיבוי סינונים – אדמין)
  getFilterSwitches: async (): Promise<FilterSwitches> => {
    const response = await apiClient.get<FilterSwitches>('/api/admin/filter-switches');
    return response.data;
  },
  updateFilterSwitches: async (switches: Partial<FilterSwitches>): Promise<FilterSwitches> => {
    const response = await apiClient.put<FilterSwitches>('/api/admin/filter-switches', switches);
    return response.data;
  },

  /** לוג אבטחה: רשימת צפיות בהקלטות תעבורה (משתמש + זמן). session_id אופציונלי לסינון. */
  listTrafficRecordingViews: async (params?: { session_id?: number }): Promise<{ views: TrafficRecordingViewLogEntry[] }> => {
    const response = await apiClient.get<{ views: TrafficRecordingViewLogEntry[] }>('/api/admin/traffic-recording-views', { params: params?.session_id != null ? { session_id: params.session_id } : undefined });
    return response.data;
  },
};

export interface FilterSwitches {
  url_policy: boolean;
  text_filter: boolean;
  image_filter: boolean;
  embedded_image_filter: boolean;
  file_download_filter: boolean;
  surf_widget: boolean;
}

export interface GlobalRule {
  id: number;
  domain_pattern: string;
  path_pattern?: string;
  action: string;
  include_subdomains: boolean;
  tags?: string[];
  text_filter_enabled?: boolean;
  image_filter_enabled?: boolean;
  file_filter_enabled?: boolean;
  created_at: number;
  updated_at: number;
  display_url?: string;
}

export interface GlobalRuleCreate {
  url: string;
  action?: string;
  include_subdomains?: boolean;
  tags?: string[];
  text_filter_enabled?: boolean;
  image_filter_enabled?: boolean;
  file_filter_enabled?: boolean;
}

export interface GlobalRuleUpdate {
  url?: string;
  action?: string;
  include_subdomains?: boolean;
  tags?: string[];
  text_filter_enabled?: boolean;
  image_filter_enabled?: boolean;
  file_filter_enabled?: boolean;
}

export interface AllowedFileItem {
  url: string;
  created_at: number;
}

/** רשומה בלוג אבטחה – צפייה בהקלטת תעבורה */
export interface TrafficRecordingViewLogEntry {
  id: number;
  traffic_session_id: number;
  user_id: number;
  viewed_at: number;
  email?: string;
  first_name?: string;
  last_name?: string;
}
