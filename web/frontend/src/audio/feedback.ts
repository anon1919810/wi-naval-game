import { interactionAudio, storedMuted, type SoundCue } from './interactionAudio';
/** Control feedback here; confirmed outcomes stay with their response handlers. */
export function controlCue(control: Element): SoundCue | null {
  if (control.closest('[inert], [hidden], [data-audio="manual"]') || control.matches(':disabled, [aria-disabled="true"]')) return null;
  if (control.closest('.ff-rail, .ff-ruler') || control.matches('.ff-title-link, .ff-title-action')) return null;
  if (control.closest('.stage-index')) return control.getAttribute('href') === window.location.hash ? null : 'detent';
  if (control.getAttribute('data-audio') === 'detent') return 'detent';
  if (control.matches('.nav-item, [role="tab"]')) return control.matches('[aria-current], [aria-selected="true"]') ? null : 'detent';
  if (control.matches('summary, [aria-expanded], [aria-pressed]')) return 'detent';
  if (control.matches('a')) return (control.getAttribute('href') ?? '').startsWith('#') ? null : 'touch';
  return control.matches('button, input[type="submit"], input[type="button"]') ? 'touch' : null;
}
export function installInteractionFeedback(): () => void {
  interactionAudio.setMuted(storedMuted());
  interactionAudio.warm();
  let active = true;
  let keyboard = false;
  const gesture = (event: Event) => {
    if (!event.isTrusted) return;
    keyboard = event instanceof KeyboardEvent && event.key === 'Tab'; interactionAudio.unlock();
  };
  const click = (event: MouseEvent) => {
    if (!event.isTrusted || event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    const target = event.target instanceof Element ? event.target : null;
    const control = target?.closest('button, a, summary, input[type="submit"], input[type="button"]');
    const cue = control ? controlCue(control) : null;
    // Capture the old selected state. React commits before this microtask; a
    // navigation/result may then supersede this lower-priority command cue.
    if (cue) queueMicrotask(() => { if (active && !event.defaultPrevented) interactionAudio.play(cue); });
  };
  const change = (event: Event) => {
    if (!event.isTrusted || !(event.target instanceof Element) || event.target.closest('[inert], [hidden], [data-audio="manual"]')) return;
    if (event.target.matches('select, input[type="checkbox"], input[type="radio"]')) interactionAudio.play('detent');
  };
  const preview = (event: Event) => {
    if (!event.isTrusted || (event.type === 'focusin' && !keyboard)) return;
    if (typeof PointerEvent !== 'undefined' && event instanceof PointerEvent && event.pointerType !== 'mouse') return;
    const target = event.target instanceof Element ? event.target : null;
    const link = target?.closest('.ff-title-link, .ff-title-action');
    if (!link || link.closest('[inert], [hidden]')) return;
    const related = (event as FocusEvent).relatedTarget;
    if (related instanceof Node && link.contains(related)) return;
    interactionAudio.play('touch', { group: 'preview' });
  };
  const hide = () => { if (document.hidden) interactionAudio.stop(); };
  const storage = (event: StorageEvent) => { if (event.key === 'formfield-preview-sound') interactionAudio.setMuted(event.newValue === 'muted'); };
  document.addEventListener('pointerdown', gesture, true); document.addEventListener('keydown', gesture, true);
  document.addEventListener('click', click, true); document.addEventListener('change', change);
  document.addEventListener('pointerover', preview); document.addEventListener('focusin', preview);
  document.addEventListener('visibilitychange', hide);
  window.addEventListener('storage', storage); window.addEventListener('pagehide', interactionAudio.dispose);
  return () => {
    active = false;
    document.removeEventListener('pointerdown', gesture, true); document.removeEventListener('keydown', gesture, true);
    document.removeEventListener('click', click, true); document.removeEventListener('change', change);
    document.removeEventListener('pointerover', preview); document.removeEventListener('focusin', preview);
    document.removeEventListener('visibilitychange', hide);
    window.removeEventListener('storage', storage); window.removeEventListener('pagehide', interactionAudio.dispose);
    interactionAudio.dispose();
  };
}
export function outcome(cue: 'resolve' | 'hold' | 'detent'): void { interactionAudio.play(cue, { group: 'result' }); }
export function transitionCue(kind: string): void {
  const local = kind === 'theme' || kind.startsWith('sheet');
  interactionAudio.play(local ? 'detent' : 'passage', { group: local ? 'command' : 'transition' });
}
