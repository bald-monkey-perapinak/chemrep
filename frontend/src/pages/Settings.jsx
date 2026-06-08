import { useState, useEffect, useRef } from 'react'
import { api } from '../utils/api'
import { useStore } from '../store/useStore'

export default function Settings() {
  const teacher     = useStore(s => s.teacher)
  const setTeacher  = useStore(s => s.setTeacher)
  const showToast   = useStore(s => s.showToast)

  const [name, setName]         = useState(teacher?.full_name || '')
  const [platform, setPlatform] = useState(teacher?.default_vcs_platform || 'zoom')
  const [saving, setSaving]     = useState(false)

  const [voiceStatus, setVoiceStatus]   = useState(null)
  const [cloning, setCloning]           = useState(false)
  const [cloneFiles, setCloneFiles]     = useState([])
  const fileRef = useRef()

  useEffect(() => {
    api.voiceStatus().then(setVoiceStatus).catch(() => {})
  }, [])

  async function saveProfile() {
    setSaving(true)
    try {
      const updated = await api.updateMe({ full_name: name, default_vcs_platform: platform })
      setTeacher(updated)
      showToast('Профиль сохранён')
    } catch (e) {
      showToast('Ошибка: ' + e.message)
    } finally {
      setSaving(false)
    }
  }

  async function cloneVoice() {
    if (!cloneFiles.length) { showToast('Добавьте аудиофайлы'); return }
    setCloning(true)
    try {
      const result = await api.cloneVoice(cloneFiles)
      setVoiceStatus({ has_clone: true, voice_id: result.voice_id, voice_name: result.voice_name, model_ready: true })
      showToast('Голос клонирован!')
      setCloneFiles([])
    } catch (e) {
      showToast('Ошибка клонирования: ' + e.message)
    } finally {
      setCloning(false)
    }
  }

  async function deleteVoice() {
    if (!confirm('Удалить клонированный голос?')) return
    try {
      await api.deleteVoice()
      setVoiceStatus(v => ({ ...v, has_clone: false, voice_id: null, model_ready: false }))
      showToast('Голос удалён')
    } catch (e) {
      showToast('Ошибка: ' + e.message)
    }
  }

  return (
    <div style={{ maxWidth: 560 }}>
      {/* Профиль */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 16 }}>
          <i className="ti ti-user" style={{ marginRight: 8 }}></i>Профиль
        </div>
        <div className="form-group">
          <label className="form-label">Полное имя</label>
          <input className="form-input" value={name} onChange={e => setName(e.target.value)} />
        </div>
        <div className="form-group">
          <label className="form-label">Платформа по умолчанию</label>
          <div className="platform-toggle">
            <button className={`platform-btn${platform === 'zoom' ? ' active' : ''}`}
              onClick={() => setPlatform('zoom')}>Zoom</button>
            <button className={`platform-btn${platform === 'yandex' ? ' active' : ''}`}
              onClick={() => setPlatform('yandex')}>Яндекс Телемост</button>
          </div>
        </div>
        <button className="btn btn-primary" onClick={saveProfile} disabled={saving}>
          {saving ? 'Сохраняем…' : 'Сохранить'}
        </button>
      </div>

      {/* Голос */}
      <div className="card">
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
          <i className="ti ti-microphone" style={{ marginRight: 8 }}></i>Клонирование голоса
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
          Загрузите записи вашего голоса (MP3 или WAV, суммарно от 1 минуты).
          Бот будет говорить вашим голосом на уроках.
        </div>

        {voiceStatus?.has_clone ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className="badge badge-active">
              <i className="ti ti-check" style={{ marginRight: 4 }}></i>Голос клонирован
            </span>
            <button className="btn btn-sm btn-danger" onClick={deleteVoice}>
              <i className="ti ti-trash"></i> Удалить
            </button>
          </div>
        ) : (
          <>
            <input ref={fileRef} type="file" accept="audio/*" multiple style={{ display: 'none' }}
              onChange={e => setCloneFiles(Array.from(e.target.files))} />
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
              <button className="btn btn-sm" onClick={() => fileRef.current.click()}>
                <i className="ti ti-upload"></i> Выбрать файлы
              </button>
              {cloneFiles.length > 0 && (
                <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                  {cloneFiles.length} файл(ов) выбрано
                </span>
              )}
            </div>
            <button className="btn btn-primary btn-sm" onClick={cloneVoice}
              disabled={cloning || !cloneFiles.length}>
              {cloning ? 'Создаём клон…' : 'Клонировать голос'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
