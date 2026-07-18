'use client';

/** Live structural preview: parses the draft JSON client-side and renders the
 * scene graph as an outline — scenes, elements, and where each branch leads.
 * The full drag-and-drop visual builder is a later slice; this gives authors
 * the map while they write. */
import { Badge, Card, Eyebrow } from '@/components/ui';

interface SceneShape {
  title?: string;
  next?: string | null;
  ending?: { id?: string; title?: string } | null;
  elements?: Array<Record<string, unknown>>;
}

function elementSummary(element: Record<string, unknown>): string {
  const type = String(element.type ?? '?');
  if (type === 'dialogue') {
    const npc = element.npc ? String(element.npc) : 'narrator';
    return `dialogue — ${npc}`;
  }
  if (type === 'media') return `media — ${String(element.kind ?? '?')}`;
  if (type === 'choice') {
    const options = Array.isArray(element.options) ? element.options : [];
    const targets = options
      .map((o) => (o as Record<string, unknown>).goto)
      .filter(Boolean);
    return `choice "${String(element.id ?? '?')}" — ${options.length} option(s)` +
      (targets.length ? ` → ${targets.join(', ')}` : '');
  }
  if (type === 'challenge') {
    return `challenge "${String(element.id ?? '?')}" — ${String(element.challenge_type ?? '?')}`;
  }
  return type;
}

export function MissionOutline({ raw }: { raw: string }) {
  let parsed: Record<string, unknown> | null = null;
  let parseError = '';
  try {
    parsed = JSON.parse(raw) as Record<string, unknown>;
  } catch (e) {
    parseError = e instanceof Error ? e.message : 'Invalid JSON';
  }

  if (parseError || !parsed) {
    return (
      <Card>
        <Eyebrow tone="muted">Outline</Eyebrow>
        <p className="mt-2 text-sm text-danger">
          Outline paused — the JSON doesn&apos;t parse yet.
        </p>
        <p className="mt-1 font-mono text-xs text-ink-muted">{parseError}</p>
      </Card>
    );
  }

  const scenes = (parsed.scenes ?? {}) as Record<string, SceneShape>;
  const start = String(parsed.start_scene ?? '');
  const sceneIds = Object.keys(scenes);

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <Eyebrow tone="muted">Outline</Eyebrow>
        <Badge>{sceneIds.length} scene(s)</Badge>
      </div>
      <p className="font-display text-sm font-semibold">
        {String(parsed.title ?? 'Untitled')}
      </p>
      <ul className="flex flex-col gap-3">
        {sceneIds.map((sceneId) => {
          const scene = scenes[sceneId] ?? {};
          const elements = Array.isArray(scene.elements) ? scene.elements : [];
          return (
            <li key={sceneId} className="border-l-2 border-line pl-3">
              <p className="font-mono text-xs text-ink">
                <span className="text-accent">{sceneId}</span>
                {sceneId === start && <span className="ml-2 text-ink-muted">(start)</span>}
                {scene.next && <span className="text-ink-muted"> → {scene.next}</span>}
                {scene.ending && (
                  <span className="ml-2 text-success">
                    ◆ ending: {scene.ending.id ?? '?'}
                  </span>
                )}
              </p>
              {scene.title && <p className="text-xs text-ink-muted">{scene.title}</p>}
              <ul className="mt-1 flex flex-col gap-0.5">
                {elements.map((element, index) => (
                  <li key={index} className="font-mono text-[11px] text-ink-muted">
                    {String(index + 1).padStart(2, '0')} {elementSummary(element)}
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
