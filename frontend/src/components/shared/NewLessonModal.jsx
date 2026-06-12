import { useState, useMemo } from 'react'
import Modal from './Modal'
import { useStore } from '../../store/useStore'

const DURATIONS = [
  { value: 30,  label: '30 мин' },
  { value: 45,  label: '45 мин' },
  { value: 60,  label: '1 час' },
  { value: 90,  label: '1.5 часа' },
  { value: 120, label: '2 часа' },
]

function detectPlatform(link) {
  if (!link) return 'zoom'
  const lower = link.toLowerCase()
  if (lower.includes('zoom.us') || lower.includes('zoom.com')) return 'zoom'
  if (lower.includes('telemost.yandex') || lower.includes('yandex.ru')) return 'yandex'
  return 'zoom'
}

export default function NewLessonModal({ onClose, defaultDate }) {
  const addLesson  = useStore(s => s.addLesson)
  const students   = useStore(s => s.students)
  const showToast  = useStore(s => s.showToast)

  const [studentId, setStudentId] = useState('')
  const [date, setDate]           = useState(defaultDate || new Date().toISOString().slice(0, 10))
  const [time, setTime]           = useState('16:00')
  const [duration, setDuration]   = useState(60)
  const [link, setLink]           = useState('')
  const [err, setErr]             = useState('')

  const platform = useMemo(() => detectPlatform(link), [link])

  async function save() {
    if (!date || !time) { setErr('Укажите дату и время'); return }
    if (!link.trim()) { setErr('Укажите ссылку на конференцию'); return }
    const student = students.find(s => s.id === studentId)
    await addLesson({
      student_id:   studentId || null,
      student_name: student?.full_name || null,
      scheduled_at: new Date(`${date}T${time}:00`).toISOString(),
      duration_min: duration,
      vcs_platform: platform,
      vcs_link:     link.trim(),
      topic_name:   null,
    })
    showToast('Занятие создано')
    onClose()
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
        <label className="form-label">Длительность</label>
        <select className="form-input" value={duration} onChange={e => setDuration(+e.target.value)}>
          {DURATIONS.map(d => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label">Ссылка на конференцию</label>
        <input className="form-input" value={link} onChange={e => setLink(e.target.value)}
          placeholder="https://zoom.us/j/... или https://telemost.yandex.ru/j/..." />
        {link && (
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
            Платформа: <strong>{platform === 'zoom' ? 'Zoom' : 'Яндекс Телемост'}</strong>
          </div>
        )}
      </div>

      {err && <div className="form-err">{err}</div>}
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={save}>Создать занятие</button>
      </div>
    </Modal>
  )
}
