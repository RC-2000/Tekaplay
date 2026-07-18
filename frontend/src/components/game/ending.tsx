'use client';

import { motion, useReducedMotion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { Button, Eyebrow } from '@/components/ui';
import type { HUD } from '@/lib/types';

export function EndingScreen({
  ending,
  hud,
  onReplay,
}: {
  ending: { id: string; title?: string; description?: string };
  hud: HUD;
  onReplay: () => void;
}) {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center"
    >
      <Eyebrow>Transmission complete</Eyebrow>
      <h1 className="font-display text-4xl font-semibold">
        {ending.title ?? 'Mission complete'}
      </h1>
      {ending.description && <p className="text-ink-muted">{ending.description}</p>}
      <p className="font-mono text-sm text-accent">+{hud.xp_earned} XP earned</p>
      <div className="mt-2 flex gap-3">
        <Button onClick={() => router.push('/dashboard')}>Back to dashboard</Button>
        <Button variant="ghost" onClick={onReplay}>Replay mission</Button>
      </div>
    </motion.div>
  );
}
