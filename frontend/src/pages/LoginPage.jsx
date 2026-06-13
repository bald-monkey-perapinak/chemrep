import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../utils/api'

export default function LoginPage({ onLogin }) {
  const [email, setEmail]     = useState('')
  const [password, setPass]   = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  async function submit(e) {
    e.preventDefault()
    if (!email || !password) { setError('Заполните все поля'); return }
    setLoading(true); setError('')
    try {
      await api.login(email, password)
      onLogin()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: 'var(--color-bg)',
    }}>
      <form onSubmit={submit} style={{
        background: 'var(--color-surface)', border: '0.5px solid var(--color-border)',
        borderRadius: 16, padding: '36px 40px', width: 380,
      }}>
        <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 4 }}>
          ХимТьютор
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 28 }}>
          Войдите в кабинет преподавателя
        </div>

        <div className="form-group">
          <label className="form-label">Email</label>
          <input className="form-input" type="email" value={email}
            onChange={e => setEmail(e.target.value)} placeholder="teacher@school.ru" autoFocus />
        </div>

        <div className="form-group">
          <label className="form-label">Пароль</label>
          <input className="form-input" type="password" value={password}
            onChange={e => setPass(e.target.value)} placeholder="Минимум 8 символов" />
        </div>

        {error && (
          <div style={{ fontSize: 12, color: '#A32D2D', marginBottom: 12 }}>{error}</div>
        )}

        <button className="btn btn-primary" type="submit" disabled={loading}
          style={{ width: '100%', justifyContent: 'center', marginBottom: 12 }}>
          {loading ? 'Подождите…' : 'Войти'}
        </button>

        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', textAlign: 'center' }}>
          Нет аккаунта?{' '}
          <Link to="/register" style={{ color: 'var(--color-primary, #4f6ef7)', fontSize: 12 }}>
            Зарегистрироваться
          </Link>
        </div>
      </form>
    </div>
  )
}
