import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../utils/api'

export default function RegisterPage({ onRegister }) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr]           = useState('')
  const [loading, setLoading]   = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setErr('')

    if (!fullName.trim()) { setErr('Введите имя'); return }
    if (!email.trim()) { setErr('Введите email'); return }
    if (password.length < 8) { setErr('Пароль минимум 8 символов'); return }

    setLoading(true)
    try {
      await api.register(email, password, fullName.trim())
      await api.login(email, password)
      onRegister()
    } catch (e) {
      setErr(e.message || 'Ошибка регистрации')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--color-bg, #f5f5f5)',
    }}>
      <form onSubmit={handleSubmit} style={{
        width: 360, padding: 32, background: '#fff', borderRadius: 12,
        boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
      }}>
        <h2 style={{ margin: '0 0 4px', fontSize: 20 }}>Регистрация</h2>
        <p style={{ margin: '0 0 20px', fontSize: 13, color: '#888' }}>
          Создайте аккаунт преподавателя
        </p>

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 13, marginBottom: 4, color: '#555' }}>Полное имя</label>
          <input
            className="form-input"
            value={fullName}
            onChange={e => setFullName(e.target.value)}
            placeholder="Иванов Иван Иванович"
            autoFocus
          />
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 13, marginBottom: 4, color: '#555' }}>Email</label>
          <input
            className="form-input"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="teacher@mail.ru"
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, marginBottom: 4, color: '#555' }}>Пароль</label>
          <input
            className="form-input"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Минимум 8 символов"
          />
        </div>

        {err && (
          <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fee', borderRadius: 6, fontSize: 13, color: '#c00' }}>
            {err}
          </div>
        )}

        <button
          className="btn btn-primary"
          type="submit"
          disabled={loading}
          style={{ width: '100%', marginBottom: 12 }}
        >
          {loading ? 'Регистрация...' : 'Зарегистрироваться'}
        </button>

        <p style={{ textAlign: 'center', fontSize: 13, color: '#888' }}>
          Уже есть аккаунт?{' '}
          <Link to="/login" style={{ color: 'var(--color-primary, #4f6ef7)' }}>Войти</Link>
        </p>
      </form>
    </div>
  )
}
