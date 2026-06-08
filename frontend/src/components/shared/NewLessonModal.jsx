import { useState } from 'react'
import Modal from './Modal'
import { useStore } from '../../store/useStore'

export default function NewLessonModal({ onClose, defaultDate }) {
  const addLesson   = useStore(s => s.addLesson)
  const students    = useStore(s => s.students)
  const showToast   = useStore(s => s.showToast)

  const [studentId, setStudentId] = useState('')
  const [date, setDate]           = useState(defaultDate || new Date().toISOString().slice(0, 10))
  const [time, setTime]           = useState('16:00')
  const [platform, setPlatform]   = useState('zoom')
  const [link, setLink]           = useState('')
  const [err, setErr]             = useState('')
  const [saving, setSaving]       = useState(false)

  async function save() {
    if (!date || !time) { setErr('Укажите дату и время'); return }
    setSaving(true); setErr('')
    try {
      const scheduled_at = new Date(`${date}T${time}:00`).toISOString()
      await addLesson({
        student_id:   studentId || null,
        scheduled_at,
        vcs_platform: platform,
        vcs_link:     link.trim() || null,
      })
      showToast('Занятие создано')
      onClose()
    } catch (e) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal onClose={onClose}>
      <div className="modal-header">
        <span className="modal-title">Новое занятие</span>
        <button className="btn btn-sm" onClick={onClose}><i className="ti ti-x"></i></button>
      </div>

      <div className="form-group">
        <label className="form-label">Ученик</label>
        <select className="form-input" value={studentId} onChange={e => setStudentId(e.target.value)}>
          <option value="">— Не выбран —</option>
          {students.map(s => (
            <option key={s.id} value={s.id}>{s.full_name}{s.grade ? ` (${s.grade} кл.)` : ''}</option>
          ))}
        </select>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Дата</label>
          <input className="form-input" type="date" value={date} onChange={e => setDate(e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Время</label>
          <input className="form-input" type="time" value={time} onChange={e => setTime(e.target.value)} />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Платформа</label>
        <div className="platform-toggle">
          <button className={`platform-btn${platform === 'zoom' ? ' active' : ''}`}
            onClick={() => setPlatform('zoom')}>Zoom</button>
          <button className={`platform-btn${platform === 'yandex' ? ' active' : ''}`}
            onClick={() => setPlatform('yandex')}>Яндекс Телемост</button>
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Ссылка на конференцию</label>
        <input className="form-input" value={link} onChange={e => setLink(e.target.value)}
          placeholder={platform === 'zoom' ? 'https://zoom.us/j/...' : 'https://telemost.yandex.ru/j/...'} />
      </div>

      {err && <div className="form-err">{err}</div>}
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? 'Создаём…' : 'Создать занятие'}
        </button>
      </div>
    </Modal>
  )
}
