/**
 * When admin is "managing" a client: managedUserId and phone for display.
 * Pass managedUserId to profile/rules/schedules API calls.
 */
import { create } from 'zustand';

interface ManagedUserState {
  managedUserId: number | null;
  managedUserPhone: string | null;
  setManagedUser: (userId: number, phone: string) => void;
  clearManagedUser: () => void;
}

export const useManagedUserStore = create<ManagedUserState>((set) => ({
  managedUserId: null,
  managedUserPhone: null,
  setManagedUser: (userId, phone) => set({ managedUserId: userId, managedUserPhone: phone }),
  clearManagedUser: () => set({ managedUserId: null, managedUserPhone: null }),
}));
