import { useState } from 'react'
import { api } from '../utils/api'

export default function LoginPage({ onLogin }) {
  const [mode, setMode]       = useState('login')   // 'login' | 'register'
  const [email, setEmail]     = useState('')
  const [password, setPass]   = useState('')
  const [name, setName]       = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  async function submit() {
    if (!email || !password) { setError('Заполните все поля'); return }
    setLoading(true); setError('')
    try {
      if (mode === 'login') {
        await api.login(email, password)
      } else {
        if (!name) { setError('Введите имя'); setLoading(false); return }
        await api.register(email, password, name)
        await api.login(email, password)
      }
      onLogin()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: 'var(--color-bg)',
    }}>
      <div style={{
        background: 'var(--color-surface)', border: '0.5px solid var(--color-border)',
        borderRadius: 16, padding: '36px 40px', width: 380,
      }}>
        <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 4 }}>
          ХимТьютор
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 28 }}>
          {mode === 'login' ? 'Войдите в кабинет преподавателя' : 'Создайте аккаунт'}
        </div>

        {mode === 'register' && (
          <div className="form-group">
            <label className="form-label">Полное имя</label>
            <input className="form-input" value={name} onChange={e => setName(e.target.value)}
              placeholder="Иванова Алина Петровна" autoFocus />
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Email</label>
          <input className="form-input" type="email" value={email}
            onChange={e => setEmail(e.target.value)} placeholder="teacher@school.ru"
            onKeyDown={e => e.key === 'Enter' && submit()}
            autoFocus={mode === 'login'} />
        </div>

        <div className="form-group">
          <label className="form-label">Пароль</label>
          <input className="form-input" type="password" value={password}
            onChange={e => setPass(e.target.value)} placeholder="Минимум 8 символов"
            onKeyDown={e => e.key === 'Enter' && submit()} />
        </div>

        {error && (
          <div style={{ fontSize: 12, color: '#A32D2D', marginBottom: 12 }}>{error}</div>
        )}

        <button className="btn btn-primary" onClick={submit} disabled={loading}
          style={{ width: '100%', justifyContent: 'center', marginBottom: 12 }}>
          {loading ? 'Подождите…' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
        </button>

        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', textAlign: 'center' }}>
          {mode === 'login' ? (
            <>Нет аккаунта? <button className="link-btn" style={{ fontSize: 12 }}
              onClick={() => { setMode('register'); setError('') }}>Зарегистрироваться</button></>
          ) : (
            <>Уже есть аккаунт? <button className="link-btn" style={{ fontSize: 12 }}
              onClick={() => { setMode('login'); setError('') }}>Войти</button></>
          )}
        </div>
      </div>
    </div>
  )
}
