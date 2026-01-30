/**
 * Profiles store using Zustand
 */
import { create } from 'zustand';
import type { Profile } from '../api/profiles';
import { profilesApi } from '../api/profiles';
import { resolverApi } from '../api/rules';

interface ProfilesState {
  profiles: Profile[];
  currentProfile: Profile | null;
  loading: boolean;
  error: string | null;
  fetchProfiles: (managedUserId?: number) => Promise<void>;
  setCurrentProfile: (profile: Profile | null) => void;
  createProfile: (name: string, mode: 'whitelist' | 'blacklist', managedUserId?: number) => Promise<Profile | null>;
  updateProfile: (id: number, name?: string, mode?: 'whitelist' | 'blacklist', managedUserId?: number) => Promise<void>;
  deleteProfile: (id: number, managedUserId?: number) => Promise<void>;
}

export const useProfilesStore = create<ProfilesState>((set, get) => ({
  profiles: [],
  currentProfile: null,
  loading: false,
  error: null,

  fetchProfiles: async (managedUserId?: number) => {
    set({ loading: true, error: null });
    try {
      const profiles = await profilesApi.list(managedUserId);
      set({ profiles, loading: false });
      // Set default profile if none selected
      if (!get().currentProfile && profiles.length > 0) {
        const defaultProfile = profiles.find(p => p.is_default) || profiles[0];
        set({ currentProfile: defaultProfile });
      }
    } catch (error: unknown) {
      set({ error: error instanceof Error ? error.message : String(error), loading: false });
    }
  },

  setCurrentProfile: (profile) => {
    set({ currentProfile: profile });
  },

  createProfile: async (name: string, mode: 'whitelist' | 'blacklist', managedUserId?: number) => {
    set({ loading: true, error: null });
    try {
      const newProfile = await profilesApi.create({ name, mode }, managedUserId);
      set((state) => ({
        profiles: [...state.profiles, newProfile],
        loading: false,
      }));
      return newProfile;
    } catch (error: unknown) {
      set({ error: error instanceof Error ? error.message : String(error), loading: false });
      throw error;
    }
  },

  updateProfile: async (id: number, name?: string, mode?: 'whitelist' | 'blacklist', managedUserId?: number) => {
    set({ loading: true, error: null });
    try {
      const updated = await profilesApi.update(id, { name, mode }, managedUserId);
      set((state) => ({
        profiles: state.profiles.map((p) => (p.id === id ? updated : p)),
        currentProfile: state.currentProfile?.id === id ? updated : state.currentProfile,
        loading: false,
      }));
      await resolverApi.sync(managedUserId);
    } catch (error: unknown) {
      set({ error: error instanceof Error ? error.message : String(error), loading: false });
      throw error;
    }
  },

  deleteProfile: async (id: number, managedUserId?: number) => {
    set({ loading: true, error: null });
    try {
      await profilesApi.delete(id, managedUserId);
      set((state) => {
        const newProfiles = state.profiles.filter((p) => p.id !== id);
        return {
          profiles: newProfiles,
          currentProfile: state.currentProfile?.id === id 
            ? (newProfiles[0] || null)
            : state.currentProfile,
          loading: false,
        };
      });
    } catch (error: unknown) {
      set({ error: error instanceof Error ? error.message : String(error), loading: false });
      throw error;
    }
  },
}));
