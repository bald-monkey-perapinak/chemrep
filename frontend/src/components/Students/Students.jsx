import { useEffect, useState } from 'react'
import { useStore } from '../../store/useStore'
import Modal from '../shared/Modal'

export default function Students() {
  const students        = useStore(s => s.students)
  const studentsLoading = useStore(s => s.studentsLoading)
  const fetchStudents   = useStore(s => s.fetchStudents)
  const addStudent      = useStore(s => s.addStudent)
  const deleteStudent   = useStore(s => s.deleteStudent)
  const showToast       = useStore(s => s.showToast)

  const [open, setOpen]     = useState(false)
  const [name, setName]     = useState('')
  const [email, setEmail]   = useState('')
  const [grade, setGrade]   = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr]       = useState('')

  useEffect(() => { fetchStudents() }, [])

  async function save() {
    if (!name.trim()) { setErr('Введите имя'); return }
    setSaving(true); setErr('')
    try {
      await addStudent({ full_name: name.trim(), email: email || null, grade: grade ? +grade : null })
      setOpen(false); setName(''); setEmail(''); setGrade('')
      showToast('Ученик добавлен')
    } catch (e) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function remove(id, name) {
    if (!confirm(`Удалить ученика «${name}»?`)) return
    try {
      await deleteStudent(id)
      showToast('Ученик удалён')
    } catch (e) {
      showToast('Ошибка: ' + e.message)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ fontSize: 14, color: 'var(--color-text-muted)' }}>
          {students.length} {students.length === 1 ? 'ученик' : students.length < 5 ? 'ученика' : 'учеников'}
        </span>
        <button className="btn btn-primary btn-sm" onClick={() => setOpen(true)}>
          <i className="ti ti-plus"></i> Добавить ученика
        </button>
      </div>

      {studentsLoading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Загрузка…</div>
      ) : students.length === 0 ? (
        <div className="empty-state card">
          <i className="ti ti-users"></i>
          Учеников нет. Добавьте первого.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="lessons-table">
            <thead>
              <tr>
                <th>Имя</th><th>Email</th><th>Класс</th><th></th>
              </tr>
            </thead>
            <tbody>
              {students.map(s => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500 }}>{s.full_name}</td>
                  <td style={{ color: 'var(--color-text-muted)' }}>{s.email || '—'}</td>
                  <td>{s.grade ? `${s.grade} класс` : '—'}</td>
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => remove(s.id, s.full_name)}>
                      <i className="ti ti-trash"></i>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <Modal onClose={() => setOpen(false)} width="380px">
          <div className="modal-header">
            <span className="modal-title">Новый ученик</span>
            <button className="btn btn-sm" onClick={() => setOpen(false)}><i className="ti ti-x"></i></button>
          </div>
          <div className="form-group">
            <label className="form-label">Полное имя</label>
            <input className="form-input" value={name} onChange={e => setName(e.target.value)}
              placeholder="Петров Михаил Александрович" autoFocus />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Email</label>
              <input className="form-input" type="email" value={email}
                onChange={e => setEmail(e.target.value)} placeholder="student@mail.ru" />
            </div>
            <div className="form-group">
              <label className="form-label">Класс</label>
              <input className="form-input" type="number" min="1" max="11" value={grade}
                onChange={e => setGrade(e.target.value)} placeholder="10" />
            </div>
          </div>
          {err && <div className="form-err">{err}</div>}
          <div className="form-actions">
            <button className="btn" onClick={() => setOpen(false)}>Отмена</button>
            <button className="btn btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Сохраняем…' : 'Добавить'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
