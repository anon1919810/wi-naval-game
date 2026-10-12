import { useEffect, useRef, useState } from 'react';
import { outcome } from '../audio/feedback';
import { useLanguage } from './LanguageProvider';

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
 *
 * The two states are worded, not merely coloured: a Chinese visitor is told in
 * Chinese that nothing was copied, and is pointed at the same address that always
 * works. A refused clipboard is a browser's answer, and the message never claims
 * more than what happened.
 */
export function Contact() {
  const { t } = useLanguage();
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

  return <section className="ff-contact" aria-labelledby="ff-contact-title" data-ff-section={t('contact.section')}>
    <h2 id="ff-contact-title" tabIndex={-1}>{t('contact.title')}</h2>
    <p className="ff-contact-note">{t('contact.note')}</p>
    <div className="ff-contact-actions">
      {/* An address is an address in both languages, so it is marked as Latin
          text rather than translated. */}
      <a className="ff-contact-mail" href={`mailto:${CONTACT_EMAIL}`} lang="en">{CONTACT_EMAIL}</a>
      <button type="button" onClick={copy} className="ff-contact-copy">{t('contact.copy')}</button>
      <a className="ff-contact-profile" href={CONTACT_PROFILE} target="_blank" rel="noopener noreferrer" lang="en">{t('contact.github')} <span aria-hidden="true">↗</span></a>
    </div>
    {state === 'copied' && <p className="ff-contact-status" role="status">{t('contact.copied', { email: CONTACT_EMAIL })}</p>}
    {state === 'unavailable' && <p className="ff-contact-status ff-contact-status--failed" role="alert">{t('contact.failed')}</p>}
  </section>;
}
