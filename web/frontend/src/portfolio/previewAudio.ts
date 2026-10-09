/** Compatibility seam for the rail and reading controller; one shared player. */
import { interactionAudio, SOUND_KEY, storedMuted } from '../audio/interactionAudio';
export { storedMuted };
export const PREVIEW_SOUND_KEY = SOUND_KEY;
export type PreviewVoice = 'work' | 'about' | 'section';
export interface PreviewSound {
  readonly muted: boolean;
  readonly unlocked: boolean;
  setMuted(muted: boolean): void;
  unlock(): void;
  tap(voice?: PreviewVoice): boolean;
  dispose(): void;
}
export function createPreviewSound(): PreviewSound {
  return {
    get muted() { return interactionAudio.muted; },
    get unlocked() { return interactionAudio.unlocked; },
    setMuted: interactionAudio.setMuted,
    unlock: interactionAudio.unlock,
    tap: voice => voice === 'section'
      ? interactionAudio.play('detent', { group: 'reading', volume: .32 })
      : interactionAudio.play('touch', { group: 'preview' }),
    dispose: () => interactionAudio.stop(),
  };
}
