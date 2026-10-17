/**
 * Per-video review (user) and the human review queue (admin).
 */
import apiClient from './client';

export interface VideoReview {
  video_key?: string;
  source_url?: string;
  page_url?: string | null;
  status: 'pending' | 'processing' | 'allowed' | 'blocked' | 'review' | 'error' | null;
  requested_at?: number;
  updated_at?: number;
  duration_sec?: number | null;
  frames_sampled?: number | null;
  frames_analyzed?: number | null;
  blocked_at_sec?: number | null;
  reason?: string | null;
  has_thumb?: boolean;
}

export interface BlockedMedia {
  media_key: string;
  media_url: string;
  page_url: string | null;
  content_type: string | null;
  seen_at: number;
  review_status: VideoReview['status'];
}

export interface ReviewImage {
  image_hash: string;
  image_url: string | null;
  status: string;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  updated_at: number;
  attempts: number;
  flags: Record<string, boolean>;
  has_thumb: boolean;
}

export const videoReviewApi = {
  request: (url: string, pageUrl?: string | null): Promise<VideoReview> =>
    apiClient.post('/api/video-reviews', { url, page_url: pageUrl || null }).then((r) => r.data),
  status: (url: string): Promise<VideoReview> =>
    apiClient.get('/api/video-reviews/status', { params: { url } }).then((r) => r.data),
  recentBlocked: (pageUrl?: string | null): Promise<BlockedMedia[]> =>
    apiClient
      .get('/api/video-reviews/recent-blocked', { params: pageUrl ? { page_url: pageUrl } : {} })
      .then((r) => r.data.items),
};

export const reviewQueueApi = {
  summary: (): Promise<{ images_review: number; images_failed: number; videos: Record<string, number> }> =>
    apiClient.get('/api/admin/review/summary').then((r) => r.data),
  images: (status: 'review' | 'error' | 'blocked'): Promise<ReviewImage[]> =>
    apiClient.get('/api/admin/review/images', { params: { status } }).then((r) => r.data.items),
  /** Thumbnails need the auth header, so they are fetched as blobs (an <img src> cannot send it). */
  imageThumb: (hash: string): Promise<string> =>
    apiClient
      .get(`/api/admin/review/images/${hash}/thumb`, { responseType: 'blob' })
      .then((r) => URL.createObjectURL(r.data)),
  decideImage: (hash: string, decision: 'allow' | 'block'): Promise<void> =>
    apiClient.post(`/api/admin/review/images/${hash}`, { decision }).then(() => undefined),
  videos: (status?: string): Promise<VideoReview[]> =>
    apiClient.get('/api/admin/review/videos', { params: status ? { status } : {} }).then((r) => r.data.items),
  videoThumb: (key: string): Promise<string> =>
    apiClient
      .get('/api/admin/review/videos/thumb', { params: { key }, responseType: 'blob' })
      .then((r) => URL.createObjectURL(r.data)),
  decideVideo: (key: string, decision: 'allow' | 'block' | 'requeue'): Promise<VideoReview> =>
    apiClient.post('/api/admin/review/videos/decide', { key, decision }).then((r) => r.data),
};

export const VIDEO_STATUS_LABELS: Record<string, string> = {
  pending: 'ממתין בתור',
  processing: 'בבדיקה',
  allowed: 'אושר – פתוח לכולם',
  blocked: 'נחסם',
  review: 'ממתין לבודק אנושי',
  error: 'שגיאה',
};
