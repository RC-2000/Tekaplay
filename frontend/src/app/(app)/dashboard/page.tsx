'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  Badge, Button, Card, EmptyState, ErrorState, Eyebrow, ProgressBar, Skeleton,
} from '@/components/ui';
import { api, post } from '@/lib/api';
import { useAuthStore } from '@/lib/auth-store';
import type {
  DefinitionOut, ProgressOut, SessionView, StreakOut, UnlockedAchievement, XpSummary,
} from '@/lib/types';

export default function DashboardPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const xp = useQuery({ queryKey: ['xp'], queryFn: () => api<XpSummary>('/xp/me') });
  const streak = useQuery({
    queryKey: ['streak'],
    queryFn: () => api<StreakOut>('/progress/me/streak'),
  });
  const progress = useQuery({
    queryKey: ['progress'],
    queryFn: () => api<ProgressOut[]>('/progress/me'),
  });
  const achievements = useQuery({
    queryKey: ['achievements-me'],
    queryFn: () => api<UnlockedAchievement[]>('/achievements/me'),
  });
  const definitions = useQuery({
    queryKey: ['definitions'],
    queryFn: () => api<DefinitionOut[]>('/runtime/definitions'),
  });

  const resume = useMutation({
    mutationFn: (definitionId: string) =>
      post<SessionView>('/runtime/sessions', { definition_id: definitionId }),
    onSuccess: (view) => router.push(`/play/${view.session_id}`),
  });

  const bySlug = new Map((definitions.data ?? []).map((d) => [d.slug, d]));

  return (
    <div className="flex flex-col gap-8">
      <div>
        <Eyebrow>Dashboard // {user?.display_name ?? 'operative'}</Eyebrow>
        <h1 className="mt-1 font-display text-3xl font-semibold">Mission status</h1>
      </div>

      <section className="grid gap-4 sm:grid-cols-3" aria-label="Stats">
        <Card>
          <Eyebrow tone="muted">Rank</Eyebrow>
          {xp.isPending ? (
            <Skeleton className="mt-2 h-16" />
          ) : xp.isError ? (
            <ErrorState message="Rank unavailable." onRetry={() => xp.refetch()} />
          ) : (
            <>
              <p className="mt-1 font-display text-4xl font-semibold">
                LV {xp.data.level}
              </p>
              <p className="mb-2 mt-1 font-mono text-xs text-ink-muted">
                {xp.data.total_xp} / {xp.data.next_level_at} XP
              </p>
              <ProgressBar
                value={xp.data.total_xp - xp.data.level_floor}
                max={xp.data.next_level_at - xp.data.level_floor}
                label="XP toward next level"
              />
            </>
          )}
        </Card>
        <Card>
          <Eyebrow tone="muted">Streak</Eyebrow>
          {streak.isPending ? (
            <Skeleton className="mt-2 h-16" />
          ) : (
            <>
              <p className="mt-1 font-display text-4xl font-semibold">
                {streak.data?.current_streak ?? 0}
                <span className="ml-1 text-base text-ink-muted">days</span>
              </p>
              <p className="mt-1 font-mono text-xs text-ink-muted">
                best {streak.data?.longest_streak ?? 0}
              </p>
            </>
          )}
        </Card>
        <Card>
          <Eyebrow tone="muted">Achievements</Eyebrow>
          {achievements.isPending ? (
            <Skeleton className="mt-2 h-16" />
          ) : (
            <>
              <p className="mt-1 font-display text-4xl font-semibold">
                {achievements.data?.length ?? 0}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {(achievements.data ?? []).slice(0, 3).map((a) => (
                  <Badge key={a.id} tone="accent">{a.title}</Badge>
                ))}
              </div>
            </>
          )}
        </Card>
      </section>

      <section aria-label="Continue learning" className="flex flex-col gap-3">
        <h2 className="font-display text-xl font-semibold">Continue learning</h2>
        {progress.isPending ? (
          <Skeleton className="h-24" />
        ) : (progress.data ?? []).length === 0 ? (
          <EmptyState
            title="No missions on record"
            hint="Pick your first mission from the library — your progress, XP, and streak start there."
            action={<Button onClick={() => router.push('/library')}>Open the library</Button>}
          />
        ) : (
          <div className="flex flex-col gap-2">
            {(progress.data ?? []).map((p) => {
              const definition = bySlug.get(p.slug);
              const mastery = p.questions_answered
                ? Math.round((p.questions_correct / p.questions_answered) * 100)
                : 0;
              return (
                <Card key={p.id} className="flex flex-wrap items-center gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {definition?.title ?? p.slug}
                    </p>
                    <p className="font-mono text-xs text-ink-muted">
                      {p.status === 'completed'
                        ? `completed ×${p.completions} // best ending: ${p.best_ending ?? '—'}`
                        : 'in progress'}{' '}
                      // mastery {mastery}%
                    </p>
                  </div>
                  {p.status === 'completed' && <Badge tone="success">Cleared</Badge>}
                  {definition && (
                    <Button
                      size="sm"
                      variant={p.status === 'completed' ? 'ghost' : 'primary'}
                      disabled={resume.isPending}
                      onClick={() => resume.mutate(definition.id)}
                    >
                      {p.status === 'completed' ? 'Replay' : 'Resume'}
                    </Button>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
