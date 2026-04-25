import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api/endpoints'

export function LoginPage() {
  const nav = useNavigate()
  const [mode,    setMode]    = useState<'login' | 'register'>('login')
  const [email,   setEmail]   = useState('')
  const [name,    setName]    = useState('')
  const [pwd,     setPwd]     = useState('')
  const [err,     setErr]     = useState('')
  const [busy,    setBusy]    = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      if (mode === 'login') {
        await login(email, pwd)
      } else {
        if (name.trim().length < 2) throw new Error('Indica o teu nome')
        await register(email, name, pwd)
      }
      nav('/')
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : 'Erro inesperado')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="orb">₿</span>
          <div>
            <strong>Apex Crypto</strong>
            <small>trading dashboard</small>
          </div>
        </div>

        <h1 className="auth-title">
          {mode === 'login' ? 'Entrar' : 'Criar conta'}
        </h1>
        <p className="auth-sub">
          {mode === 'login'
            ? 'Acede ao teu scanner, watchlist e portfolio.'
            : 'Cria conta para personalizar alertas e gerir posições.'}
        </p>

        <form onSubmit={submit} className="auth-form">
          {mode === 'register' && (
            <label>
              <span>Nome</span>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="O teu nome" required />
            </label>
          )}
          <label>
            <span>Email</span>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="rui@example.com" required />
          </label>
          <label>
            <span>Password</span>
            <input type="password" value={pwd} onChange={e => setPwd(e.target.value)} placeholder="••••••••" required minLength={6} />
          </label>

          {err && <p className="err-msg">{err}</p>}

          <button className="btn auth-submit" type="submit" disabled={busy}>
            {busy ? '…' : (mode === 'login' ? 'Entrar' : 'Criar conta')}
          </button>
        </form>

        <p className="auth-toggle">
          {mode === 'login' ? 'Sem conta?' : 'Já tens conta?'}
          {' '}
          <button className="link-btn" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setErr('') }}>
            {mode === 'login' ? 'Cria uma' : 'Entra aqui'}
          </button>
        </p>
      </div>
    </div>
  )
}
