'use client';

import { cn } from '@/components/ui';
import type { VersionStatus } from '@/lib/types';

const TONES: Record<VersionStatus, string> = {
  draft: 'border-line text-ink-muted',
  in_review: 'border-accent/60 text-accent',
  approved: 'border-success/60 text-success',
  published: 'border-success/60 bg-success/10 text-success',
  superseded: 'border-line text-ink-muted opacity-70',
  rejected: 'border-danger/60 text-danger',
};

export function StatusBadge({ status }: { status: VersionStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider',
        TONES[status] ?? 'border-line text-ink-muted',
      )}
    >
      {status.replace('_', ' ')}
    </span>
  );
}
