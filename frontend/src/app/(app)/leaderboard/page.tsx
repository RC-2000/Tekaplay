'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, EmptyState, ErrorState, Eyebrow, Skeleton, cn } from '@/components/ui';
import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/auth-store';
import type { LeaderboardEntry } from '@/lib/types';

export default function LeaderboardPage() {
  const user = useAuthStore((s) => s.user);
  const board = useQuery({
    queryKey: ['leaderboard'],
    queryFn: () => api<LeaderboardEntry[]>('/xp/leaderboard?limit=50'),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Eyebrow>Leaderboard // top operatives</Eyebrow>
        <h1 className="mt-1 font-display text-3xl font-semibold">Rankings</h1>
      </div>
      {board.isPending ? (
        <Skeleton className="h-64" />
      ) : board.isError ? (
        <ErrorState message="Rankings did not load." onRetry={() => board.refetch()} />
      ) : (board.data ?? []).length === 0 ? (
        <EmptyState title="No XP earned yet" hint="Finish a mission to claim rank 1." />
      ) : (
        <Card className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left font-mono text-xs uppercase tracking-wider text-ink-muted">
                <th className="px-4 py-3">Rank</th>
                <th className="px-4 py-3">Operative</th>
                <th className="px-4 py-3 text-right">Level</th>
                <th className="px-4 py-3 text-right">XP</th>
              </tr>
            </thead>
            <tbody>
              {(board.data ?? []).map((entry) => (
                <tr
                  key={entry.user_id}
                  className={cn(
                    'border-b border-line last:border-0',
                    entry.user_id === user?.id && 'bg-accent-soft/60',
                  )}
                >
                  <td className="px-4 py-2.5 font-mono text-accent">
                    {String(entry.rank).padStart(2, '0')}
                  </td>
                  <td className="px-4 py-2.5">
                    {entry.display_name}
                    {entry.user_id === user?.id && (
                      <span className="ml-2 font-mono text-xs text-ink-muted">(you)</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">LV {entry.level}</td>
                  <td className="px-4 py-2.5 text-right font-mono">{entry.total_xp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
