/**
 * Schedules API endpoints
 */
import apiClient from './client';

export interface Schedule {
  id: number;
  profile_id: number;
  days_bitmask: number;
  from_time: string | null;
  to_time: string | null;
  created_at: number;
  updated_at: number;
}

export interface ScheduleCreate {
  days: number[]; // 0-6 for א-ש
  from_time?: string; // HH:MM (optional)
  to_time?: string; // HH:MM (optional)
}

export interface ScheduleUpdate {
  days?: number[];
  from_time?: string;
  to_time?: string;
}

export const schedulesApi = {
  list: async (profileId: number): Promise<Schedule[]> => {
    const response = await apiClient.get<Schedule[]>(`/api/profiles/${profileId}/schedules`);
    return response.data;
  },

  get: async (id: number): Promise<Schedule> => {
    const response = await apiClient.get<Schedule>(`/api/schedules/${id}`);
    return response.data;
  },

  create: async (profileId: number, data: ScheduleCreate): Promise<Schedule> => {
    const response = await apiClient.post<Schedule>(`/api/profiles/${profileId}/schedules`, data);
    return response.data;
  },

  update: async (id: number, data: ScheduleUpdate): Promise<Schedule> => {
    const response = await apiClient.put<Schedule>(`/api/schedules/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/schedules/${id}`);
  },
};
