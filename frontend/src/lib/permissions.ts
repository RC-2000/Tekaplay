'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/auth-store';

/** The caller's effective permission codes. UI gating only — the backend
 * enforces authorization on every route regardless. */
export function usePermissions() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const query = useQuery({
    queryKey: ['permissions'],
    queryFn: () => api<string[]>('/users/me/permissions'),
    enabled: Boolean(accessToken),
    staleTime: 60_000,
  });
  const codes = new Set(query.data ?? []);
  return {
    loading: query.isPending,
    has: (code: string) => codes.has(code),
    isAuthor: codes.has('content.author'),
    isPublisher: codes.has('content.publish'),
  };
}
