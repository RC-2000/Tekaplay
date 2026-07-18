'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  Badge, Button, Card, EmptyState, ErrorState, Eyebrow, Skeleton,
} from '@/components/ui';
import { api, post } from '@/lib/api';
import type { CertificationNode, DefinitionOut, SessionView } from '@/lib/types';

export default function LibraryPage() {
  const router = useRouter();
  const library = useQuery({
    queryKey: ['library'],
    queryFn: () => api<CertificationNode[]>('/content/library'),
  });
  const definitions = useQuery({
    queryKey: ['definitions'],
    queryFn: () => api<DefinitionOut[]>('/runtime/definitions'),
  });

  const start = useMutation({
    mutationFn: (definitionId: string) =>
      post<SessionView>('/runtime/sessions', { definition_id: definitionId }),
    onSuccess: (view) => router.push(`/play/${view.session_id}`),
  });

  if (library.isPending || definitions.isPending) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </div>
    );
  }
  if (library.isError) {
    return <ErrorState message="The library did not load." onRetry={() => library.refetch()} />;
  }

  const tree = library.data ?? [];
  const catalogued = new Set(
    tree.flatMap((c) =>
      c.campaigns.flatMap((cp) =>
        cp.courses.flatMap((co) => co.missions.map((m) => m.definition_id)),
      ),
    ),
  );
  const uncatalogued = (definitions.data ?? []).filter((d) => !catalogued.has(d.id));

  return (
    <div className="flex flex-col gap-8">
      <div>
        <Eyebrow>Library // all certifications</Eyebrow>
        <h1 className="mt-1 font-display text-3xl font-semibold">Choose a mission</h1>
      </div>

      {tree.length === 0 && uncatalogued.length === 0 && (
        <EmptyState
          title="Nothing published yet"
          hint="When creators publish missions, they appear here."
        />
      )}

      {tree.map((cert) => (
        <section key={cert.id} className="flex flex-col gap-4" aria-label={cert.title}>
          <div>
            <Eyebrow>{cert.category || 'certification'}</Eyebrow>
            <h2 className="font-display text-2xl font-semibold">{cert.title}</h2>
            {cert.description && (
              <p className="mt-1 max-w-2xl text-sm text-ink-muted">{cert.description}</p>
            )}
          </div>
          {cert.campaigns.map((campaign) => (
            <div key={campaign.id} className="flex flex-col gap-3">
              <Eyebrow tone="muted">
                {cert.slug} // {campaign.title}
              </Eyebrow>
              {campaign.courses.map((course) => (
                <Card key={course.id} className="flex flex-col gap-2">
                  <p className="font-medium">{course.title}</p>
                  <ul className="flex flex-col divide-y divide-line">
                    {course.missions.map((mission, index) => (
                      <li key={mission.id} className="flex items-center gap-3 py-2">
                        <span className="font-mono text-xs text-ink-muted">
                          M{String(index + 1).padStart(2, '0')}
                        </span>
                        <span className="flex-1">{mission.title}</span>
                        {mission.definition_id ? (
                          <Button
                            size="sm"
                            disabled={start.isPending}
                            onClick={() => start.mutate(mission.definition_id!)}
                          >
                            Play
                          </Button>
                        ) : (
                          <Badge>In development</Badge>
                        )}
                      </li>
                    ))}
                  </ul>
                </Card>
              ))}
            </div>
          ))}
        </section>
      ))}

      {uncatalogued.length > 0 && (
        <section className="flex flex-col gap-3" aria-label="All missions">
          <Eyebrow tone="muted">uncatalogued transmissions</Eyebrow>
          <div className="grid gap-3 sm:grid-cols-2">
            {uncatalogued.map((definition) => (
              <Card key={definition.id} className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{definition.title}</p>
                  <p className="font-mono text-xs text-ink-muted">{definition.certification || definition.slug}</p>
                </div>
                <Button size="sm" disabled={start.isPending}
                        onClick={() => start.mutate(definition.id)}>
                  Play
                </Button>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
