'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Button, Card, Eyebrow, Input } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/lib/auth-store';

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await register(email, password, displayName);
      router.replace('/dashboard');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not create the account.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6">
      <Eyebrow>QuestForge // enlist</Eyebrow>
      <h1 className="font-display text-2xl font-semibold">Create your account</h1>
      <Card>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Input label="Display name" name="display_name" value={displayName}
                 onChange={(e) => setDisplayName(e.target.value)} required maxLength={120} />
          <Input label="Email" name="email" type="email" autoComplete="email"
                 value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input label="Password" name="password" type="password"
                 autoComplete="new-password" minLength={10} value={password}
                 onChange={(e) => setPassword(e.target.value)} required
                 error={password.length > 0 && password.length < 10
                   ? 'At least 10 characters' : undefined} />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? 'Creating…' : 'Create account'}
          </Button>
        </form>
      </Card>
      <p className="text-sm text-ink-muted">
        Already enlisted?{' '}
        <Link href="/login" className="text-accent underline-offset-2 hover:underline">
          Log in
        </Link>
      </p>
    </main>
  );
}
