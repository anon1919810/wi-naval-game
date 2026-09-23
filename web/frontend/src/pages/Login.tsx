import { useState } from 'react';

import * as api from '../api';

export function Login({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [phase, setPhase] = useState<'email' | 'code'>('email');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (phase === 'email') {
        await api.requestCode(email.trim());
        setPhase('code');
      } else {
        await api.verifyCode(email.trim(), code);
        onAuthenticated();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '暂时无法完成操作，请稍后重试');
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-page">
    <div className="auth-background" aria-hidden="true"><span /><span /><span /></div>
    <div className="auth-layout">
      <section className="auth-intro">
        <div className="brand brand--large"><span className="brand-mark" aria-hidden="true" />Plimsoll</div>
        <div className="eyebrow">VESSEL DESIGN WORKSPACE / 舰船计算工作台</div>
        <h1>让每一个结果<br /><em>都有来处。</em></h1>
        <p>保存舰船方案，切换载荷，复核稳性与性能。设计假设、工程估算与未知输入始终清楚可见。</p>
        <div className="auth-rule"><span>参考水线</span><span>z = 0 m</span></div>
      </section>
      <section className="auth-panel" aria-label="邮箱登录">
        <span className="section-kicker">01 / 进入工作空间</span>
        <h2>{phase === 'email' ? '继续使用邮箱' : '输入邮箱验证码'}</h2>
        <p className="muted">{phase === 'email' ? '首次验证邮箱时将自动建立账户。项目默认仅你可见。' : `验证码已发往 ${email}。10 分钟内有效，仅可使用一次。`}</p>
        <form onSubmit={submit}>
          {phase === 'email' ? <label className="field-label">邮箱地址
            <input autoComplete="email" autoFocus required type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="name@example.com" />
          </label> : <label className="field-label">六位验证码
            <input autoComplete="one-time-code" autoFocus required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={event => setCode(event.target.value)} placeholder="000000" />
          </label>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button--primary button--wide" type="submit" disabled={busy}>{busy ? '请稍候…' : phase === 'email' ? '发送验证码' : '验证并进入'}</button>
        </form>
        {phase === 'code' && <button className="text-button" type="button" onClick={() => { setPhase('email'); setCode(''); setError(''); }}>更换邮箱地址</button>}
        <p className="auth-note">Plimsoll 使用计算模型辅助设计研究，不以“计算完成”代替史实验证或适航认证。</p>
      </section>
    </div>
  </main>;
}
