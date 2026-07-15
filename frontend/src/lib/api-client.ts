/**
 * Single HTTP client for the backend. All frontend data access goes through
 * this module + React Query — components never call fetch directly, and the
 * standard error envelope is decoded in exactly one place.
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public retryable: boolean,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    credentials: 'include',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const err = body?.error;
    throw new ApiError(
      err?.code ?? 'unknown_error',
      err?.message ?? `Request failed (${res.status})`,
      res.status,
      err?.retryable ?? false,
      err?.details ?? {},
    );
  }
  return res.json() as Promise<T>;
}
