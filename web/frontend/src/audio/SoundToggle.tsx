import { useSyncExternalStore } from 'react';
import { interactionAudio } from './interactionAudio';
import { useShellCopy } from '../i18n/shell';
import './sound.css';

/**
 * The one sound control, shared by the public shell and the workspace.
 *
 * This component is mounted by the eager public shell as well as by the
 * workspace, so its workspace wording is read from the shared chrome dictionary
 * rather than from the workspace one: reading the bigger dictionary here would
 * pull every editor, report and laboratory string into the chunk the home page
 * loads. The public labels are passed in rather than looked up, because the
 * public dictionary is the shell's own and the public shell is the only surface
 * that renders them.
 *
 * Both are optional: with no props at all and no provider this is the English
 * control it has always been, which is what keeps a standalone render and the
 * workspace's own tests unchanged. The mute itself is shared state
 * (`interactionAudio`), not local state: the public toggle and the workspace
 * toggle always say the same thing about the same speaker.
 */
export function SoundToggle({
  workspace = false,
  label,
  onLabel,
  offLabel,
}: {
  /** The workspace control names itself from the shared chrome dictionary. */
  workspace?: boolean;
  /** Public accessible name. Defaults to the English "Sound". */
  label?: string;
  /** Public title while muted. Defaults to "Turn sound on". */
  onLabel?: string;
  /** Public title while unmuted. Defaults to "Mute sound". */
  offLabel?: string;
}) {
  const w = useShellCopy();
  const muted = useSyncExternalStore(interactionAudio.subscribe, () => interactionAudio.muted);
  const name = workspace ? w('sound.label') : label ?? 'Sound';
  const toOn = workspace ? w('sound.on') : onLabel ?? 'Turn sound on';
  const toOff = workspace ? w('sound.off') : offLabel ?? 'Mute sound';
  return <button className={workspace ? 'workspace-sound icon-button' : 'ff-preview-sound'} data-audio="manual"
    type="button" aria-label={name} aria-pressed={!muted}
    title={muted ? toOn : toOff}
    onClick={() => {
      interactionAudio.setMuted(!muted);
      if (muted) { interactionAudio.unlock(); interactionAudio.play('touch'); }
    }}>
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="M3 8h3l4-3.4v10.8L6 12H3z" />
      <path className="ff-preview-sound-wave" d="M13 7.4a3.4 3.4 0 0 1 0 5.2" />
      <path className="ff-preview-sound-slash" d="M3.5 16.5 16.5 3.5" />
    </svg>
  </button>;
}