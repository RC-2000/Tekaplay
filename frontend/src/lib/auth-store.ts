'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, configureAuth, post } from '@/lib/api';
import type { TokenPair, UserOut } from '@/lib/types';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserOut | null;
  hydrated: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string, displayName: string): Promise<void>;
  loadMe(): Promise<void>;
  logout(): Promise<void>;
  setTokens(tokens: { access: string; refresh: string }): void;
  clear(): void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      hydrated: false,

      setTokens: ({ access, refresh }) =>
        set({ accessToken: access, refreshToken: refresh }),
      clear: () => set({ accessToken: null, refreshToken: null, user: null }),

      async login(email, password) {
        const pair = await post<TokenPair>('/auth/login', { email, password });
        get().setTokens({ access: pair.access_token, refresh: pair.refresh_token });
        await get().loadMe();
      },

      async register(email, password, displayName) {
        await post('/auth/register', { email, password, display_name: displayName });
        await get().login(email, password);
      },

      async loadMe() {
        const user = await api<UserOut>('/users/me');
        set({ user });
      },

      async logout() {
        const refresh = get().refreshToken;
        if (refresh) {
          await post('/auth/logout', { refresh_token: refresh }).catch(() => undefined);
        }
        get().clear();
      },
    }),
    {
      name: 'tekaplay-auth',
      partialize: (s) => ({
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
        user: s.user,
      }),
      onRehydrateStorage: () => () => {
        useAuthStore.setState({ hydrated: true });
      },
    },
  ),
);

// Wire the HTTP client to the store (single composition point).
configureAuth({
  getAccess: () => useAuthStore.getState().accessToken,
  getRefresh: () => useAuthStore.getState().refreshToken,
  setTokens: (tokens) => useAuthStore.getState().setTokens(tokens),
  clear: () => useAuthStore.getState().clear(),
});
