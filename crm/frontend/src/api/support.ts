/**
 * Support tickets API (פניות משתמשים)
 */
import apiClient from './client';

export interface SupportTicket {
  id: number;
  user_id: number;
  subject: string;
  content: string;
  created_at: number;
  updated_at: number;
  content_preview?: string;
  user_first_name?: string;
  user_last_name?: string;
  user_phone?: string;
  user_avatar_url?: string;
  replies_count?: number;
  unread_replies_count?: number;
  attachments?: SupportAttachmentItem[];
}

export interface SupportAttachmentItem {
  name: string;
  url: string;
}

export interface SupportTicketCreate {
  subject: string;
  content: string;
  attachments?: SupportAttachmentItem[];
}

export interface SupportReply {
  id: number;
  ticket_id: number;
  author_id: number;
  content: string;
  created_at: number;
  author_first_name?: string;
  author_last_name?: string;
  author_avatar_url?: string;
  is_unread?: boolean;
  attachments?: SupportAttachmentItem[];
}

export interface SupportReplyCreate {
  content: string;
  attachments?: SupportAttachmentItem[];
}

export const supportApi = {
  uploadFile: async (
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<{ url: string; name: string }> => {
    const form = new FormData();
    form.append('file', file);
    const response = await apiClient.post('/api/support/upload', form, {
      onUploadProgress: onProgress
        ? (ev) => {
            if (ev.total && ev.total > 0) {
              const p = Math.round((ev.loaded / ev.total) * 100);
              onProgress(Math.min(100, p));
            }
          }
        : undefined,
    });
    let body = response?.data;
    if (typeof body === 'string') {
      try {
        body = JSON.parse(body) as Record<string, unknown>;
      } catch {
        throw new Error('תגובת ההעלאה לא תקינה');
      }
    }
    if (!body || typeof body !== 'object') throw new Error('תגובת ההעלאה לא תקינה');
    const url = (body as { url?: string }).url ?? (body as { data?: { url: string } }).data?.url;
    const name = (body as { name?: string }).name ?? (body as { data?: { name: string } }).data?.name ?? file.name;
    if (url == null || url === '') throw new Error('ההעלאה לא החזירה קישור');
    return { url: String(url), name: String(name) };
  },

  createTicket: async (data: SupportTicketCreate): Promise<SupportTicket> => {
    const response = await apiClient.post<SupportTicket>('/api/support/tickets', data);
    return response.data;
  },

  listTickets: async (params?: {
    page?: number;
    page_size?: number;
    sort_order?: string;
    search?: string;
    /** 'mine' = רק הפניות שלי (גם לאדמין); לא מועבר = לאדמין כל הפניות */
    scope?: 'mine' | 'all';
  }): Promise<{ tickets: SupportTicket[]; total: number }> => {
    const response = await apiClient.get<{ tickets: SupportTicket[]; total: number }>(
      '/api/support/tickets',
      { params }
    );
    return response.data;
  },

  getTicket: async (id: number): Promise<SupportTicket> => {
    const response = await apiClient.get<SupportTicket>(`/api/support/tickets/${id}`);
    return response.data;
  },

  listReplies: async (ticketId: number): Promise<SupportReply[]> => {
    const response = await apiClient.get<SupportReply[]>(
      `/api/support/tickets/${ticketId}/replies`
    );
    return response.data;
  },

  addReply: async (ticketId: number, data: SupportReplyCreate): Promise<SupportReply> => {
    const response = await apiClient.post<SupportReply>(
      `/api/support/tickets/${ticketId}/replies`,
      data
    );
    return response.data;
  },

  getStats: async (): Promise<{ tickets_with_replies: number; admin_tickets_with_replies?: number }> => {
    const response = await apiClient.get<{ tickets_with_replies: number; admin_tickets_with_replies?: number }>(
      '/api/support/stats'
    );
    return response.data;
  },

  deleteTicket: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/support/tickets/${id}`);
  },
};
