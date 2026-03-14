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
  /** Check before create: exact match (rule + identical), same-domain rules, and proposed_rule for conflict UI. */
  checkCreateGlobalRule: async (data: GlobalRuleCreate): Promise<{
    exact_match: { rule: GlobalRule; identical: boolean } | null;
    same_domain_rules: GlobalRule[];
    proposed_rule: { domain_pattern: string; path_pattern: string; action: string; include_subdomains: boolean; tags: string[]; text_filter_enabled: boolean; image_filter_enabled: boolean; file_filter_enabled: boolean };
  }> => {
    const response = await apiClient.post<{
      exact_match: { rule: GlobalRule; identical: boolean } | null;
      same_domain_rules: GlobalRule[];
      proposed_rule: { domain_pattern: string; path_pattern: string; action: string; include_subdomains: boolean; tags: string[]; text_filter_enabled: boolean; image_filter_enabled: boolean; file_filter_enabled: boolean };
    }>('/api/admin/global-rules/check-create', data);
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

  // Site injections (הזרקת קוד והסתרת תוכן לאתר – אדמין)
  listSiteInjections: async (): Promise<SiteInjection[]> => {
    const response = await apiClient.get<SiteInjection[]>('/api/admin/site-injections');
    return response.data;
  },
  createSiteInjection: async (data: SiteInjectionCreate): Promise<SiteInjection> => {
    const response = await apiClient.post<SiteInjection>('/api/admin/site-injections', data);
    return response.data;
  },
  getSiteInjection: async (id: number): Promise<SiteInjection> => {
    const response = await apiClient.get<SiteInjection>(`/api/admin/site-injections/${id}`);
    return response.data;
  },
  updateSiteInjection: async (id: number, data: SiteInjectionUpdate): Promise<SiteInjection> => {
    const response = await apiClient.put<SiteInjection>(`/api/admin/site-injections/${id}`, data);
    return response.data;
  },
  deleteSiteInjection: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/admin/site-injections/${id}`);
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
  pdf_filter_text: boolean;
  pdf_filter_images: boolean;
  file_share_block: boolean;
  google_search_filter: boolean;
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
  pdf_filter_enabled?: boolean;
  video_filter_enabled?: boolean;
  surf_widget_enabled?: boolean;
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
  pdf_filter_enabled?: boolean;
  video_filter_enabled?: boolean;
  surf_widget_enabled?: boolean;
}

export interface GlobalRuleUpdate {
  url?: string;
  action?: string;
  include_subdomains?: boolean;
  tags?: string[];
  text_filter_enabled?: boolean;
  image_filter_enabled?: boolean;
  file_filter_enabled?: boolean;
  pdf_filter_enabled?: boolean;
  video_filter_enabled?: boolean;
  surf_widget_enabled?: boolean;
}

export interface AllowedFileItem {
  url: string;
  created_at: number;
}

export interface SiteInjection {
  id: number;
  domain_pattern: string;
  path_pattern?: string;
  include_subdomains: boolean;
  path_exact_only: boolean;
  head_code?: string;
  body_code?: string;
  hide_selectors_list: string[];
  enabled: boolean;
  created_at: number;
  updated_at: number;
}

export interface SiteInjectionCreate {
  url: string;
  head_code?: string;
  body_code?: string;
  hide_selectors?: string[];
  include_subdomains?: boolean;
  /** true = only this URL; false = path and all subpaths (like rules). Default true. */
  path_exact_only?: boolean;
  enabled?: boolean;
}

export interface SiteInjectionUpdate {
  url?: string;
  head_code?: string;
  body_code?: string;
  hide_selectors?: string[];
  include_subdomains?: boolean;
  path_exact_only?: boolean;
  enabled?: boolean;
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
