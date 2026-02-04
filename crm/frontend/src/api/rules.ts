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
  include_subdomains: boolean;
  tags?: string[];
  created_at: number;
  updated_at: number;
}

export interface RuleCreate {
  url: string;
  action: 'allow' | 'block';
  include_subdomains: boolean;
  tags?: string[];
}

export interface RuleUpdate {
  url?: string;
  action?: 'allow' | 'block';
  include_subdomains?: boolean;
  tags?: string[];
}

export interface TagRule {
  id: number;
  tag: string;
  state: 'allow' | 'block';
  enabled: boolean;
  created_at: number;
  updated_at: number;
}

export interface TagRuleCreate {
  tag: string;
  state: 'allow' | 'block';
  enabled?: boolean;
}

export interface TagRuleUpdate {
  tag?: string;
  state?: 'allow' | 'block';
  enabled?: boolean;
}

export const rulesApi = {
  list: async (profileId: number, managedUserId?: number): Promise<Rule[]> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.get<Rule[]>(`/api/profiles/${profileId}/rules`, { params });
    return response.data;
  },

  get: async (id: number, managedUserId?: number): Promise<Rule> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.get<Rule>(`/api/rules/${id}`, { params });
    return response.data;
  },

  create: async (profileId: number, data: RuleCreate, managedUserId?: number): Promise<Rule> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.post<Rule>(`/api/profiles/${profileId}/rules`, data, { params });
    return response.data;
  },

  update: async (id: number, data: RuleUpdate, managedUserId?: number): Promise<Rule> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.put<Rule>(`/api/rules/${id}`, data, { params });
    return response.data;
  },

  delete: async (id: number, managedUserId?: number): Promise<void> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    await apiClient.delete(`/api/rules/${id}`, { params });
  },

  /** Export rules as CSV file (download). */
  exportCsv: async (profileId: number, managedUserId?: number): Promise<void> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.get<Blob>(`/api/profiles/${profileId}/rules/export`, {
      params,
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(response.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'rules.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  },

  /** Import rules from CSV file. Returns { imported: number }. */
  importCsv: async (profileId: number, file: File, managedUserId?: number): Promise<{ imported: number }> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const form = new FormData();
    form.append('file', file);
    const response = await apiClient.post<{ imported: number }>(`/api/profiles/${profileId}/rules/import`, form, { params });
    return response.data;
  },
};

export const tagRulesApi = {
  list: async (): Promise<TagRule[]> => {
    const response = await apiClient.get<TagRule[]>('/api/tag-rules');
    return response.data;
  },

  create: async (data: TagRuleCreate): Promise<TagRule> => {
    const response = await apiClient.post<TagRule>('/api/tag-rules', data);
    return response.data;
  },

  update: async (id: number, data: TagRuleUpdate): Promise<TagRule> => {
    const response = await apiClient.put<TagRule>(`/api/tag-rules/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/tag-rules/${id}`);
  },
};

/** Core resolver state (what the proxy uses). */
export interface ResolverCoreState {
  core_mode: string | null;
  core_db_path: string | null;
  error?: string;
}

/** Active profile and rules (for current user, with schedule). */
export interface ResolverActiveState {
  profile_id: number | null;
  profile_name: string | null;
  mode: string;
  rules: unknown[];
  tag_rules: unknown[];
}

/** Sync active profile and rules to core (for proxy). Call after profile/mode change so filtering picks up immediately. */
export const resolverApi = {
  sync: async (managedUserId?: number): Promise<{ status: string; message: string } & ResolverCoreState> => {
    const params = managedUserId != null ? { managed_user_id: managedUserId } : {};
    const response = await apiClient.post<{ status: string; message: string; core_mode?: string; core_db_path?: string }>(
      '/api/resolver/sync',
      null,
      { params },
    );
    return response.data as { status: string; message: string } & ResolverCoreState;
  },

  /** Get profile mode currently stored in core (what the proxy uses). Use to verify sync. */
  getCoreMode: async (): Promise<ResolverCoreState> => {
    const response = await apiClient.get<ResolverCoreState>('/api/resolver/core-mode');
    return response.data;
  },

  /** Get currently active profile and its mode for the current user (with schedule). */
  getActiveState: async (): Promise<ResolverActiveState> => {
    const response = await apiClient.get<ResolverActiveState>('/api/resolver/active');
    return response.data;
  },

  /** Get rules in format expected by URLPolicyResolver (for current user). */
  getRules: async (): Promise<{ rules: unknown[] }> => {
    const response = await apiClient.get<{ rules: unknown[] }>('/api/resolver/rules');
    return response.data;
  },

  /**
   * Test which rule applies to a URL using the same URLPolicyResolver as the proxy.
   * Returns { state, rule?, default_mode }.
   */
  testUrl: async (url: string, type: 'html' | 'image' = 'html'): Promise<ResolverTestUrlResponse> => {
    const response = await apiClient.post<ResolverTestUrlResponse>('/api/resolver/test-url', { url: url.trim(), type });
    return response.data;
  },
};

export interface ResolverTestUrlResponse {
  state: 'allow' | 'block' | 'review';
  rule: { domain: string; path?: string; type?: string; state: string; tags?: string[] } | null;
  default_mode: string;
}
