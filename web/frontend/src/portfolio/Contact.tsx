import { useEffect, useRef, useState } from 'react';
import { outcome } from '../audio/feedback';

/** The real, public contact address and profile. Nothing here is a placeholder. */
export const CONTACT_EMAIL = 'youxiang051110@163.com';
export const CONTACT_PROFILE = 'https://github.com/anon1919810';

type CopyState = 'idle' | 'copied' | 'unavailable';

/**
 * Contact without a form and without a server. The address is a real `mailto:`
 * link, so it works even where the clipboard API does not exist, is blocked by a
 * permission policy, or rejects. “Copied” is only ever shown after
 * `writeText` has actually resolved; every other outcome says plainly that it
 * did not happen and points at the link that always works.
 */
export function Contact() {
  const [state, setState] = useState<CopyState>('idle');
  const alive = useRef(true);
  const ticket = useRef(0);
  useEffect(() => { alive.current = true; return () => { alive.current = false; ticket.current++; }; }, []);

  const copy = async () => {
    const mine = ++ticket.current;
    const clipboard = typeof navigator === 'undefined' ? undefined : navigator.clipboard;
    if (typeof clipboard?.writeText !== 'function') { setState('unavailable'); outcome('hold'); return; }
    try {
      await clipboard.writeText(CONTACT_EMAIL);
      if (!alive.current || ticket.current !== mine) return;
      setState('copied');
      outcome('resolve');
    } catch {
      if (!alive.current || ticket.current !== mine) return;
      // A rejected write means nothing reached the clipboard. Say so.
      setState('unavailable');
      outcome('hold');
    }
  };

  return <section className="ff-contact" aria-labelledby="ff-contact-title" data-ff-section="Contact">
    <h2 id="ff-contact-title" tabIndex={-1}>Get in touch</h2>
    <p className="ff-contact-note">About the work, a bug in one of the tools, or something worth building together — email is the surest way.</p>
    <div className="ff-contact-actions">
      <a className="ff-contact-mail" href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
      <button type="button" onClick={copy} className="ff-contact-copy">COPY EMAIL</button>
      <a className="ff-contact-profile" href={CONTACT_PROFILE} target="_blank" rel="noopener noreferrer">GITHUB <span aria-hidden="true">↗</span></a>
    </div>
    {state === 'copied' && <p className="ff-contact-status" role="status">COPIED — {CONTACT_EMAIL} is on your clipboard.</p>}
    {state === 'unavailable' && <p className="ff-contact-status ff-contact-status--failed" role="alert">NOT COPIED — this browser did not give the page clipboard access. The address above is a plain mail link: select it, or open it directly.</p>}
  </section>;
}
