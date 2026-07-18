'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';
import { ChallengeRenderer } from '@/components/game/challenges';
import { EndingScreen } from '@/components/game/ending';
import { CommLog, HudStrip } from '@/components/game/log';
import {
  Button, Card, ErrorState, Eyebrow, Skeleton, cn,
} from '@/components/ui';
import { ApiError, api, post } from '@/lib/api';
import { useToast } from '@/lib/toast';
import type { AnswerOut, SessionView } from '@/lib/types';

interface Feedback {
  correct: boolean;
  text: string;
}

export default function PlayPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const reduceMotion = useReducedMotion();
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const viewKey = ['session', sessionId] as const;
  const view = useQuery({
    queryKey: viewKey,
    queryFn: () => api<SessionView>(`/runtime/sessions/${sessionId}`),
  });

  const setView = (next: SessionView) => queryClient.setQueryData(viewKey, next);

  function onActionError(error: unknown) {
    toast(
      error instanceof ApiError ? error.message : 'The action did not go through.',
      'danger',
    );
  }

  const advance = useMutation({
    mutationFn: () => post<SessionView>(`/runtime/sessions/${sessionId}/advance`),
    onSuccess: (next) => {
      setFeedback(null);
      setView(next);
    },
    onError: onActionError,
  });

  const choose = useMutation({
    mutationFn: (input: { element_id: string; option_id: string }) =>
      post<SessionView>(`/runtime/sessions/${sessionId}/choose`, input),
    onSuccess: (next) => {
      setFeedback(null);
      setView(next);
    },
    onError: onActionError,
  });

  const answer = useMutation({
    mutationFn: (input: { element_id: string; response: Record<string, unknown> }) =>
      post<AnswerOut>(`/runtime/sessions/${sessionId}/answer`, input),
    onSuccess: (result) => {
      setFeedback({
        correct: result.correct,
        text: result.correct
          ? result.feedback || 'Correct. Signal locked.'
          : 'Not quite — recalibrate and try again.',
      });
      setView(result.view);
    },
    onError: onActionError,
  });

  const checkpoint = useMutation({
    mutationFn: () =>
      post(`/runtime/sessions/${sessionId}/saves`, {
        label: `Checkpoint ${new Date().toLocaleTimeString()}`,
      }),
    onSuccess: () => toast('Checkpoint saved', 'success'),
    onError: onActionError,
  });

  const replay = useMutation({
    mutationFn: (definitionId: string) =>
      post<SessionView>('/runtime/sessions', {
        definition_id: definitionId,
        replay: true,
      }),
    onSuccess: (next) => router.push(`/play/${next.session_id}`),
    onError: onActionError,
  });

  if (view.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-10 w-96 max-w-full" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (view.isError) {
    return (
      <ErrorState
        message="This session did not load. It may have ended or belong to another account."
        onRetry={() => view.refetch()}
      />
    );
  }

  const data = view.data;

  if (data.ending) {
    return (
      <EndingScreen
        ending={data.ending}
        hud={data.hud}
        onReplay={() => replay.mutate(data.definition_id)}
      />
    );
  }

  const busy = advance.isPending || choose.isPending || answer.isPending;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_260px]">
      <div className="flex flex-col gap-6">
        <div>
          <Eyebrow>
            Mission // scene {data.scene_id ?? '—'}
          </Eyebrow>
          <h1 className="mt-1 font-display text-3xl font-semibold">
            {data.scene_title ?? 'Unknown location'}
          </h1>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={`${data.scene_id}-${data.passives.length}`}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-6"
          >
            <CommLog entries={data.passives} />

            {feedback && (
              <div
                role="status"
                className={cn(
                  'rounded border px-4 py-3 text-sm',
                  feedback.correct
                    ? 'border-success/50 bg-success/10 text-success'
                    : 'border-danger/50 bg-danger/10 text-danger',
                )}
              >
                {feedback.text}
              </div>
            )}

            {data.interactive?.type === 'choice' && (
              <Card className="flex flex-col gap-3">
                <Eyebrow tone="muted">Decision point</Eyebrow>
                <p className="font-medium leading-relaxed">{data.interactive.prompt}</p>
                <div className="flex flex-col gap-2">
                  {data.interactive.options.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        choose.mutate({
                          element_id: data.interactive!.id,
                          option_id: option.id,
                        })
                      }
                      className="rounded border border-line px-4 py-3 text-left text-sm transition-colors hover:border-accent hover:bg-accent-soft disabled:opacity-50"
                    >
                      {option.text}
                    </button>
                  ))}
                </div>
              </Card>
            )}

            {data.interactive?.type === 'challenge' && (
              <Card className="flex flex-col gap-3">
                <Eyebrow tone="muted">
                  Challenge // {data.interactive.challenge_type}
                </Eyebrow>
                <ChallengeRenderer
                  key={data.interactive.id}
                  type={data.interactive.challenge_type}
                  config={data.interactive.config}
                  attemptsRemaining={data.interactive.attempts_remaining}
                  submitting={answer.isPending}
                  onSubmit={(response) =>
                    answer.mutate({ element_id: data.interactive!.id, response })
                  }
                />
              </Card>
            )}

            {data.can_advance && (
              <Button disabled={busy} onClick={() => advance.mutate()} className="self-start">
                {advance.isPending ? 'Moving…' : 'Continue'}
              </Button>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      <aside className="flex flex-col gap-3">
        <HudStrip hud={data.hud} />
        <Button
          variant="ghost"
          size="sm"
          disabled={checkpoint.isPending}
          onClick={() => checkpoint.mutate()}
        >
          {checkpoint.isPending ? 'Saving…' : 'Save checkpoint'}
        </Button>
      </aside>
    </div>
  );
}
