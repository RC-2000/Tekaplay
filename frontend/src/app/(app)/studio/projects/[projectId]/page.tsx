'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { StatusBadge } from '@/components/studio/status-badge';
import {
  Badge, Button, Card, EmptyState, ErrorState, Eyebrow, Skeleton,
} from '@/components/ui';
import { ApiError, api, post } from '@/lib/api';
import { usePermissions } from '@/lib/permissions';
import { STARTER_DEFINITION } from '@/lib/studio-template';
import { useToast } from '@/lib/toast';
import type { ProjectOut, VersionDetail, VersionOut } from '@/lib/types';

export default function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { isPublisher } = usePermissions();

  const project = useQuery({
    queryKey: ['studio-project', projectId],
    queryFn: () => api<ProjectOut>(`/content/projects/${projectId}`),
  });
  const versions = useQuery({
    queryKey: ['studio-versions', projectId],
    queryFn: () => api<VersionOut[]>(`/content/projects/${projectId}/versions`),
  });

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ['studio-versions', projectId] });
    queryClient.invalidateQueries({ queryKey: ['studio-project', projectId] });
  }

  function actionError(error: unknown) {
    toast(error instanceof ApiError ? error.message : 'The action did not go through.', 'danger');
  }

  const newDraft = useMutation({
    mutationFn: async () => {
      // Prefill from the latest version when one exists; otherwise start clean.
      const latest = (versions.data ?? [])[0];
      const definition = latest
        ? (await api<VersionDetail>(`/content/versions/${latest.id}`)).definition
        : STARTER_DEFINITION;
      return post<VersionOut>(`/content/projects/${projectId}/versions`, {
        definition,
        notes: latest ? `Draft from v${latest.version_number}` : 'First draft',
      });
    },
    onSuccess: (version) => {
      refresh();
      router.push(`/studio/versions/${version.id}`);
    },
    onError: actionError,
  });

  const publish = useMutation({
    mutationFn: (versionId: string) =>
      post<VersionOut>(`/content/versions/${versionId}/publish`),
    onSuccess: () => {
      refresh();
      toast('Published — the mission is live', 'success');
    },
    onError: actionError,
  });

  const rollback = useMutation({
    mutationFn: (versionId: string) =>
      post<VersionOut>(`/content/versions/${versionId}/rollback`),
    onSuccess: () => {
      refresh();
      toast('Rolled back — this version is live again', 'success');
    },
    onError: actionError,
  });

  if (project.isPending || versions.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-48" />
      </div>
    );
  }
  if (project.isError) {
    return <ErrorState message="This project did not load." onRetry={() => project.refetch()} />;
  }

  const data = project.data;
  const rows = versions.data ?? [];
  const busy = publish.isPending || rollback.isPending;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>
            Studio // {data.slug}
            {data.certification && <> // {data.certification}</>}
          </Eyebrow>
          <h1 className="mt-1 font-display text-3xl font-semibold">{data.title}</h1>
        </div>
        <div className="flex items-center gap-3">
          {data.live_version_id && <Badge tone="success">Live</Badge>}
          <Button disabled={newDraft.isPending} onClick={() => newDraft.mutate()}>
            {newDraft.isPending ? 'Creating…' : 'New draft'}
          </Button>
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No versions yet"
          hint="Create the first draft — it starts from a minimal valid mission you can build on."
          action={
            <Button disabled={newDraft.isPending} onClick={() => newDraft.mutate()}>
              Create first draft
            </Button>
          }
        />
      ) : (
        <Card className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left font-mono text-xs uppercase tracking-wider text-ink-muted">
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Status</th>
                <th className="hidden px-4 py-3 sm:table-cell">Notes</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((version) => (
                <tr key={version.id} className="border-b border-line align-top last:border-0">
                  <td className="px-4 py-3 font-mono">
                    v{version.version_number}
                    {version.id === data.live_version_id && (
                      <span className="ml-2 text-success">●</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={version.status} />
                    {version.review_note && (
                      <p className="mt-1 max-w-xs text-xs text-ink-muted">
                        review: {version.review_note}
                      </p>
                    )}
                  </td>
                  <td className="hidden max-w-sm px-4 py-3 text-ink-muted sm:table-cell">
                    {version.notes || '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Link href={`/studio/versions/${version.id}`}>
                        <Button size="sm" variant="ghost">
                          {version.status === 'draft' ? 'Edit' : 'Open'}
                        </Button>
                      </Link>
                      {isPublisher && version.status === 'approved' && (
                        <Button size="sm" disabled={busy}
                                onClick={() => publish.mutate(version.id)}>
                          Publish
                        </Button>
                      )}
                      {isPublisher && version.status === 'superseded' && (
                        <Button size="sm" variant="ghost" disabled={busy}
                                onClick={() => rollback.mutate(version.id)}>
                          Roll back to this
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
