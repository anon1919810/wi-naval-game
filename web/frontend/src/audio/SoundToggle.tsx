import { useSyncExternalStore } from 'react';
import { interactionAudio } from './interactionAudio';
import './sound.css';
export function SoundToggle({ workspace = false }: { workspace?: boolean }) {
  const muted = useSyncExternalStore(interactionAudio.subscribe, () => interactionAudio.muted);
  return <button className={workspace ? 'workspace-sound icon-button' : 'ff-preview-sound'} data-audio="manual"
    type="button" aria-label={workspace ? '交互音效' : 'Sound'} aria-pressed={!muted}
    title={muted ? (workspace ? '开启交互音效' : 'Turn sound on') : (workspace ? '关闭交互音效' : 'Mute sound')}
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
