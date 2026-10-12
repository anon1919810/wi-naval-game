import { useCopyMessage } from '../i18n/useCopyMessage';
import { useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { useWorkspaceCopy } from '../i18n/workspace';

export function Login({ onAuthenticated }: { onAuthenticated: () => void }) {
  const w = useWorkspaceCopy();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [phase, setPhase] = useState<'email' | 'code'>('email');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useCopyMessage();
  const audioAlive = useRef(true);
  useEffect(() => { audioAlive.current = true; return () => { audioAlive.current = false; }; }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (phase === 'email') {
        await api.requestCode(email.trim());
        if (audioAlive.current) outcome('resolve');
        setPhase('code');
      } else {
        await api.verifyCode(email.trim(), code);
        if (audioAlive.current) outcome('resolve');
        onAuthenticated();
      }
    } catch (cause) {
      if (audioAlive.current) outcome('hold');
      setError(w => cause instanceof Error ? cause.message : w('login.failedGeneric'));
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-page">
    <div className="auth-background" aria-hidden="true"><span /><span /><span /></div>
    <div className="auth-layout">
      <section className="auth-intro">
        <div className="brand brand--large"><span className="brand-mark" aria-hidden="true" />Plimsoll</div>
        <div className="eyebrow">{w('login.eyebrow')}</div>
        <h1>{w('login.titleLead')}<br /><em>{w('login.titleTail')}</em></h1>
        <p>{w('login.lede')}</p>
        <div className="auth-rule"><span>{w('login.rule')}</span><span>z = 0 m</span></div>
      </section>
      <section className="auth-panel" aria-label={w('login.panelLabel')}>
        <span className="section-kicker">{w('login.kicker')}</span>
        <h2>{phase === 'email' ? w('login.email.title') : w('login.code.title')}</h2>
        <p className="muted">{phase === 'email' ? w('login.email.note') : w('login.code.note', { email })}</p>
        <form onSubmit={submit}>
          {phase === 'email' ? <label className="field-label">{w('login.email.label')}
            <input autoComplete="email" autoFocus required type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="name@example.com" />
          </label> : <label className="field-label">{w('login.code.label')}
            <input autoComplete="one-time-code" autoFocus required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={event => setCode(event.target.value)} placeholder="000000" />
          </label>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button--primary button--wide" type="submit" disabled={busy}>{busy ? w('login.submit.wait') : phase === 'email' ? w('login.submit.email') : w('login.submit.code')}</button>
        </form>
        {phase === 'code' && <button className="text-button" type="button" onClick={() => { setPhase('email'); setCode(''); setError(''); }}>{w('login.changeEmail')}</button>}
        <p className="auth-note">{w('login.note')}</p>
      </section>
    </div>
  </main>;
}
