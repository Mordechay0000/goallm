/**
 * Rule requests API (user requests for admin to approve)
 */
import apiClient from './client';

export interface RuleRequest {
  id: number;
  user_id: number;
  request_type: 'open' | 'change' | 'file';
  url?: string;
  domain_pattern?: string;
  path_pattern?: string;
  action?: string;
  include_subdomains: boolean;
  tags?: string[];
  status: 'pending' | 'approved' | 'rejected';
  created_at: number;
  updated_at: number;
  user_phone?: string;
  approved_rule_id?: number;
  approved_profile_id?: number;
  is_from_blocked_page?: boolean;
  /** Full URL user tried to access (read-only display) */
  request_url?: string;
  /** For file requests: user description of the file */
  notes?: string;
  resolved_by_user_id?: number;
  /** Display name of admin who last approved/rejected */
  resolved_by_name?: string | null;
  text_filter_enabled?: boolean;
  image_filter_enabled?: boolean;
  file_filter_enabled?: boolean;
}

export interface RuleRequestUpdate {
  url?: string;
  action?: 'allow' | 'block';
  include_subdomains?: boolean;
  tags?: string[];
  text_filter_enabled?: boolean;
  image_filter_enabled?: boolean;
  file_filter_enabled?: boolean;
}

export interface RuleRequestCreate {
  request_type: 'open' | 'change' | 'file';
  url?: string;
  domain_pattern?: string;
  path_pattern?: string;
  action?: string;
  include_subdomains?: boolean;
  tags?: string[];
  notes?: string;
  /** Full URL user tried to access (e.g. from surf widget) */
  request_url?: string;
}

/** Shape of rule in conflict response (existing vs proposed) */
export interface RuleConflictRule {
  domain_pattern?: string;
  path_pattern?: string;
  action?: string;
  include_subdomains?: boolean;
  tags?: string[];
  text_filter_enabled?: boolean;
  image_filter_enabled?: boolean;
  file_filter_enabled?: boolean;
  id?: number;
  created_at?: number;
  updated_at?: number;
}

export const ruleRequestsApi = {
  create: async (data: RuleRequestCreate): Promise<RuleRequest> => {
    const response = await apiClient.post<RuleRequest>('/api/rule-requests', data);
    return response.data;
  },

  list: async (params?: { status_filter?: string; request_type_filter?: string; user_id?: number; search?: string; sort_by?: string; sort_order?: string; page?: number; page_size?: number }): Promise<{ requests: RuleRequest[]; total: number }> => {
    const response = await apiClient.get<{ requests: RuleRequest[]; total: number }>('/api/rule-requests', { params });
    return response.data;
  },

  get: async (id: number): Promise<RuleRequest> => {
    const response = await apiClient.get<RuleRequest>(`/api/rule-requests/${id}`);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/rule-requests/${id}`);
  },

  /** Approve request: adds rule to global list. Options: force_update / skip_rule_update when status was conflict. */
  approve: async (
    id: number,
    options?: { profileId?: number; force_update?: boolean; skip_rule_update?: boolean }
  ): Promise<
    | { status: 'approved'; request: RuleRequest; already_existed_identical?: boolean }
    | { status: 'conflict'; request: RuleRequest; existing_rule: RuleConflictRule; proposed_rule: RuleConflictRule }
  > => {
    const body: { profile_id: number | null; force_update?: boolean; skip_rule_update?: boolean } = {
      profile_id: options?.profileId ?? null,
    };
    if (options?.force_update === true) body.force_update = true;
    if (options?.skip_rule_update === true) body.skip_rule_update = true;
    const response = await apiClient.post<
      | { status: 'approved'; request: RuleRequest; already_existed_identical?: boolean }
      | { status: 'conflict'; request: RuleRequest; existing_rule: RuleConflictRule; proposed_rule: RuleConflictRule }
    >(`/api/admin/rule-requests/${id}/approve`, body);
    return response.data;
  },

  reject: async (id: number): Promise<{ status: string; request: RuleRequest }> => {
    const response = await apiClient.post<{ status: string; request: RuleRequest }>(`/api/admin/rule-requests/${id}/reject`);
    return response.data;
  },

  update: async (id: number, data: RuleRequestUpdate): Promise<RuleRequest> => {
    const response = await apiClient.put<RuleRequest>(`/api/rule-requests/${id}`, data);
    return response.data;
  },
};
