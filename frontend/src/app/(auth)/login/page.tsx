'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Button, Card, Eyebrow, Input } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/lib/auth-store';

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
      router.replace('/dashboard');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not log in — try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6">
      <Eyebrow>QuestForge // sign in</Eyebrow>
      <h1 className="font-display text-2xl font-semibold">Back to the field</h1>
      <Card>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Input label="Email" name="email" type="email" autoComplete="email"
                 value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input label="Password" name="password" type="password"
                 autoComplete="current-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} required />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? 'Logging in…' : 'Log in'}
          </Button>
        </form>
      </Card>
      <p className="text-sm text-ink-muted">
        New recruit?{' '}
        <Link href="/register" className="text-accent underline-offset-2 hover:underline">
          Create an account
        </Link>
      </p>
    </main>
  );
}
