import { useState } from 'react'
import Modal from '../shared/Modal'

export function CreateNodeModal({ title, label, placeholder, existingNames, onClose, onConfirm }) {
  const [name, setName] = useState('')
  const [err, setErr] = useState('')

  function validate(v) {
    if (!v.trim()) { setErr(''); return false }
    if (existingNames.some((n) => n.toLowerCase() === v.toLowerCase())) {
      setErr('Элемент с таким названием уже существует')
      return false
    }
    setErr('')
    return true
  }

  function handleChange(e) { setName(e.target.value); validate(e.target.value) }

  function handleConfirm() {
    if (!validate(name)) return
    onConfirm(name.trim())
  }

  return (
    <Modal onClose={onClose} width="360px">
      <div className="modal-header">
        <span className="modal-title">
          {title}
        </span>
        <button className="btn btn-sm" onClick={onClose} style={{ minWidth: 24, justifyContent: 'center' }}>×</button>
      </div>
      <div className="form-group">
        <label className="form-label">{label}</label>
        <input
          className="form-input"
          value={name}
          onChange={handleChange}
          onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
          placeholder={placeholder}
          maxLength={60}
          autoFocus
        />
        <div className="form-err">{err}</div>
      </div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={handleConfirm} disabled={!name.trim() || !!err}>
          Создать
        </button>
      </div>
    </Modal>
  )
}

export function RenameNodeModal({ currentName, existingNames, onClose, onConfirm }) {
  const [name, setName] = useState(currentName)
  const [err, setErr] = useState('')

  function validate(v) {
    if (!v.trim()) { setErr('Название не может быть пустым'); return false }
    if (existingNames.filter((n) => n !== currentName).some((n) => n.toLowerCase() === v.toLowerCase())) {
      setErr('Элемент с таким названием уже существует')
      return false
    }
    setErr('')
    return true
  }

  function handleChange(e) { setName(e.target.value); validate(e.target.value) }

  function handleConfirm() {
    if (!validate(name)) return
    onConfirm(name.trim())
  }

  return (
    <Modal onClose={onClose} width="360px">
      <div className="modal-header">
        <span className="modal-title">
          Переименовать
        </span>
        <button className="btn btn-sm" onClick={onClose} style={{ minWidth: 24, justifyContent: 'center' }}>×</button>
      </div>
      <div className="form-group">
        <label className="form-label">Новое название</label>
        <input
          className="form-input"
          value={name}
          onChange={handleChange}
          onKeyDown={(e) => e.key === 'Enter' && handleConfirm()}
          maxLength={60}
          autoFocus
        />
        <div className="form-err">{err}</div>
      </div>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Отмена</button>
        <button className="btn btn-primary" onClick={handleConfirm} disabled={!name.trim() || !!err}>
          Сохранить
        </button>
      </div>
    </Modal>
  )
}

export function DeleteNodeModal({ name, onClose, onConfirm }) {
  return (
    <Modal onClose={onClose} width="360px">
      <div className="modal-header">
        <span className="modal-title" style={{ color: '#A32D2D' }}>
          Удалить
        </span>
        <button className="btn btn-sm" onClick={onClose} style={{ minWidth: 24, justifyContent: 'center' }}>×</button>
      </div>
      <p style={{ fontSize: 14, color: 'var(--color-text-muted)', lineHeight: 1.6, marginBottom: 4 }}>
        Удалить <strong>«{name}»</strong>?{' '}
        Все вложенные папки, темы и файлы будут удалены.
      </p>
      <div className="form-actions">
        <button className="btn" onClick={onClose}>Отмена</button>
        <button className="btn btn-danger" onClick={onConfirm}>
          Удалить
        </button>
      </div>
    </Modal>
  )
}
