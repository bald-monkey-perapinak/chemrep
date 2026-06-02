import { useState } from 'react'
import Modal from '../shared/Modal'
import { useStore } from '../../store/useStore'

export default function NewLessonModal({ onClose, defaultDate }) {
  const addLesson = useStore((s) => s.addLesson)

  const [student, setStudent] = useState('')
  const [date, setDate] = useState(defaultDate || new Date().toISOString().slice(0, 10))
  const [time, setTime] = useState('16:00')
  const [topic, setTopic] = useState('')
  const [platform, setPlatform] = useState('zoom')
  const [link, setLink] = useState('')
  const [err, setErr] = useState('')

  function save() {
    if (!student.trim() || !date || !time || !topic.trim()) {
      setErr('Заполните все обязательные поля')
      return
    }
    addLesson({ student: student.trim(), date, time, topic: topic.trim(), platform, link: link.trim() || '#', status: 'upcoming' })
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
        <input className="form-input" value={student} onChange={(e) => setStudent(e.target.value)} placeholder="Имя ученика" />
      </div>

      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Дата</label>
          <input className="form-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Время</label>
          <input className="form-input" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Тема занятия</label>
        <input className="form-input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Например: Алканы — строение и свойства" />
      </div>

      <div className="form-group">
        <label className="form-label">Платформа</label>
        <div className="platform-toggle">
          <button className={`platform-btn${platform === 'zoom' ? ' active' : ''}`} onClick={() => setPlatform('zoom')}>Zoom</button>
          <button className={`platform-btn${platform === 'ya' ? ' active' : ''}`} onClick={() => setPlatform('ya')}>Яндекс Телемост</button>
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Ссылка на конференцию</label>
        <input
          className="form-input"
          value={link}
          onChange={(e) => setLink(e.target.value)}
          placeholder={platform === 'zoom' ? 'https://zoom.us/j/...' : 'https://telemost.yandex.ru/j/...'}
        />
      </div>

      {err && <div className="form-err">{err}</div>}

      <div className="form-actions">
        <button className="btn" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={save}>Создать занятие</button>
      </div>
    </Modal>
  )
}
