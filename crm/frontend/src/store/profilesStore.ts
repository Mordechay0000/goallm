/**
 * Profiles store using Zustand
 */
import { create } from 'zustand';
import type { Profile } from '../api/profiles';
import { profilesApi } from '../api/profiles';

interface ProfilesState {
  profiles: Profile[];
  currentProfile: Profile | null;
  loading: boolean;
  error: string | null;
  fetchProfiles: () => Promise<void>;
  setCurrentProfile: (profile: Profile | null) => void;
  createProfile: (name: string, mode: 'whitelist' | 'blacklist') => Promise<Profile | null>;
  updateProfile: (id: number, name?: string, mode?: 'whitelist' | 'blacklist') => Promise<void>;
  deleteProfile: (id: number) => Promise<void>;
}

export const useProfilesStore = create<ProfilesState>((set, get) => ({
  profiles: [],
  currentProfile: null,
  loading: false,
  error: null,

  fetchProfiles: async () => {
    set({ loading: true, error: null });
    try {
      const profiles = await profilesApi.list();
      set({ profiles, loading: false });
      // Set default profile if none selected
      if (!get().currentProfile && profiles.length > 0) {
        const defaultProfile = profiles.find(p => p.is_default) || profiles[0];
        set({ currentProfile: defaultProfile });
      }
    } catch (error: any) {
      set({ error: error.message, loading: false });
    }
  },

  setCurrentProfile: (profile) => {
    set({ currentProfile: profile });
  },

  createProfile: async (name: string, mode: 'whitelist' | 'blacklist') => {
    set({ loading: true, error: null });
    try {
      const newProfile = await profilesApi.create({ name, mode });
      set((state) => ({
        profiles: [...state.profiles, newProfile],
        loading: false,
      }));
      return newProfile;
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  updateProfile: async (id: number, name?: string, mode?: 'whitelist' | 'blacklist') => {
    set({ loading: true, error: null });
    try {
      const updated = await profilesApi.update(id, { name, mode });
      set((state) => ({
        profiles: state.profiles.map((p) => (p.id === id ? updated : p)),
        currentProfile: state.currentProfile?.id === id ? updated : state.currentProfile,
        loading: false,
      }));
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },

  deleteProfile: async (id: number) => {
    set({ loading: true, error: null });
    try {
      await profilesApi.delete(id);
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
    } catch (error: any) {
      set({ error: error.message, loading: false });
      throw error;
    }
  },
}));
