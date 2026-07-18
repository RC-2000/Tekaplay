/** Minimal valid game definition — passes backend validation as-is, so a new
 * draft starts green instead of broken. */
export const STARTER_DEFINITION = {
  schema_version: 1,
  title: 'Untitled mission',
  description: '',
  certification: '',
  start_scene: 'intro',
  variables: {},
  npcs: {},
  items: {},
  scenes: {
    intro: {
      title: 'Opening scene',
      elements: [
        { type: 'dialogue', npc: null, text: 'The mission begins here.' },
      ],
      ending: {
        id: 'end',
        title: 'Mission complete',
        description: 'Replace this scene with your story.',
      },
    },
  },
} as const;
