import { create } from 'zustand';
import type { User } from '../types';
import client from '../api/client';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  setToken: (token: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  isLoading: false,
  setToken: (token: string) => {
    localStorage.setItem('token', token);
    set({ token });
  },
  setUser: (user: User) => set({ user }),
  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null });
  },
  fetchMe: async () => {
    set({ isLoading: true });
    try {
      const res = await client.get<User>('/auth/me');
      set({ user: res.data });
    } finally {
      set({ isLoading: false });
    }
  },
}));
