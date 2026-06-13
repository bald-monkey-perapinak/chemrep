import { useState, useEffect } from 'react'
import { api } from '../utils/api'

export default function Settings() {
  const [activeTab, setActiveTab] = useState('profile')
  const [profile, setProfile] = useState(null)
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [backendOk, setBackendOk] = useState(null)

  useEffect(() => {
    api.me().then(d => {
      setProfile(d)
      setName(d.full_name || '')
      setBackendOk(true)
    }).catch(() => {
      setBackendOk(false)
    })
  }, [])

  async function saveName() {
    if (!name.trim()) return
    setSaving(true)
    try {
      await api.updateMe({ full_name: name })
    } catch {}
    setSaving(false)
  }

  if (backendOk === false) {
    return (
      <div style={{ maxWidth: 720 }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 15, fontWeight: 500 }}>Настройки</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 32, color: '#A32D2D', marginBottom: 12 }}>⚠</div>
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>Бэкенд недоступен</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
            Проверьте, что бэкенд запущен и доступен на <code>http://localhost:8000</code>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 720 }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 15, fontWeight: 500 }}>Настройки</div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {[
          { id: 'profile', label: 'Профиль' },
          { id: 'voice', label: 'Голос' },
          { id: 'training', label: 'Обучение' },
        ].map(tab => (
          <button
            key={tab.id}
            className={`btn ${activeTab === tab.id ? 'btn-primary' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <i className={tab.icon}></i> {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'profile' && (
        <div className="card">
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 12 }}>
            Профиль
          </div>
          <div className="form-group">
            <label className="form-label">Имя</label>
            <input
              className="form-input"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Ваше имя"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Email</label>
            <input className="form-input" value={profile?.email || ''} disabled />
          </div>
          <button className="btn btn-primary" onClick={saveName} disabled={saving}>
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      )}

      {activeTab === 'voice' && <VoiceSection />}
      {activeTab === 'training' && <TrainingSection />}
    </div>
  )
}


function VoiceSection() {
  const [status, setStatus] = useState(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    api.voiceStatus().then(setStatus).catch(() => {})
  }, [])

  async function handleClone() {
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.accept = 'audio/*'
    input.onchange = async () => {
      const files = Array.from(input.files)
      if (!files.length) return
      setUploading(true)
      try {
        await api.cloneVoice(files)
        const s = await api.voiceStatus()
        setStatus(s)
        alert('Голос успешно клонирован!')
      } catch (e) {
        alert('Ошибка: ' + e.message)
      }
      setUploading(false)
    }
    input.click()
  }

  async function handleDelete() {
    if (!confirm('Удалить клонированный голос?')) return
    try {
      await api.deleteVoice()
      setStatus({ has_clone: false, voice_id: null, voice_name: null, model_ready: false })
    } catch (e) {
      alert('Ошибка: ' + e.message)
    }
  }

  return (
    <div className="card">
      <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 12 }}>
        Клонирование голоса
      </div>
      <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 16 }}>
        Загрузите 1–25 аудиофайлов с вашим голосом (MP3/WAV, суммарно от 1 минуты).
        Бот будет говорить вашим голосом.
      </div>

      {status?.has_clone ? (
        <div>
          <div style={{ fontSize: 13, marginBottom: 8, color: '#3B6D11' }}>
            Голос клонирован: {status.voice_id}
          </div>
          <button className="btn btn-danger btn-sm" onClick={handleDelete}>
            Удалить клон
          </button>
        </div>
      ) : (
        <button className="btn btn-primary" onClick={handleClone} disabled={uploading}>
          {uploading ? 'Загрузка...' : 'Загрузить образцы голоса'}
        </button>
      )}
    </div>
  )
}


function TrainingSection() {
  const [videos, setVideos] = useState([])
  const [profile, setProfile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [polling, setPolling] = useState(null)

  useEffect(() => {
    loadVideos()
    api.getTeachingProfile().then(setProfile).catch(() => {})
  }, [])

  async function loadVideos() {
    try {
      const data = await api.listTrainingVideos()
      setVideos(data || [])
    } catch {}
  }

  async function handleUpload() {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'video/*'
    input.onchange = async () => {
      const file = input.files[0]
      if (!file) return
      setUploading(true)
      try {
        await api.uploadTrainingVideo(file)
        await loadVideos()
      } catch (e) {
        alert('Ошибка: ' + e.message)
      }
      setUploading(false)
    }
    input.click()
  }

  async function handleProcess(id) {
    try {
      await api.processTrainingVideo(id)
      startPolling()
    } catch (e) {
      alert('Ошибка: ' + e.message)
    }
  }

  function startPolling() {
    if (polling) return
    const interval = setInterval(async () => {
      await loadVideos()
      const p = await api.getTeachingProfile().catch(() => null)
      if (p) setProfile(p)
    }, 3000)
    setPolling(interval)
    setTimeout(() => {
      clearInterval(interval)
      setPolling(null)
    }, 300000)
  }

  async function handleDelete(id) {
    if (!confirm('Удалить видео?')) return
    try {
      await api.deleteTrainingVideo(id)
      await loadVideos()
    } catch (e) {
      alert('Ошибка: ' + e.message)
    }
  }

  const statusLabels = {
    uploading: 'Загружено',
    processing: 'Обработка аудио...',
    analyzing: 'Анализ стиля...',
    ready: 'Готово',
    failed: 'Ошибка',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Профиль */}
          {profile && profile.videos_count > 0 && (
        <div className="card">
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>
            Профиль стиля
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 12 }}>
            Проанализировано видео: {profile.videos_count} ·{' '}
            Суммарная длительность: {profile.total_duration_min} мин
          </div>
          {profile.custom_prompt && (
            <div style={{
              fontSize: 12,
              background: 'var(--color-bg)',
              borderRadius: 8,
              padding: 12,
              whiteSpace: 'pre-wrap',
              lineHeight: 1.5,
            }}>
              {profile.custom_prompt}
            </div>
          )}
          {Object.keys(profile.profile || {}).length > 0 && (
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {Object.entries(profile.profile).filter(([k]) => !k.includes('markers')).map(([k, v]) => (
                <span key={k} className="system-badge" title={k}>
                  {k}: {typeof v === 'object' ? (Array.isArray(v) ? v.join(', ') : JSON.stringify(v)) : String(v)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Видео */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>
            Обучающие видео
          </div>
          <button className="btn btn-primary btn-sm" onClick={handleUpload} disabled={uploading}>
            {uploading ? 'Загрузка...' : 'Загрузить видео'}
          </button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
          Загрузите видео ваших реальных занятий. Нейросеть проанализирует вашу манеру
          ведения урока, голос, структуру подачи материала и приёмы.
        </div>

        {videos.length === 0 ? (
          <div className="empty-state">
            Нет загруженных видео
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {videos.map(v => (
              <div key={v.id} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 14px',
                background: 'var(--color-bg)',
                borderRadius: 8,
              }}>
                <div style={{ fontSize: 20, color: 'var(--color-text-muted)' }}>▶</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{v.original_name}</div>
                  <div style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                    {v.size_bytes ? (v.size_bytes / 1048576).toFixed(1) + ' МБ' : '—'}
                    {v.duration_sec ? ' · ' + Math.round(v.duration_sec / 60) + ' мин' : ''}
                    {v.status === 'processing' || v.status === 'analyzing' ? ` · ${v.progress}%` : ''}
                  </div>
                </div>
                <span className={`badge ${
                  v.status === 'ready' ? 'badge-active' :
                  v.status === 'failed' ? 'badge-danger' :
                  'badge-upcoming'
                }`} style={{ fontSize: 11 }}>
                  {statusLabels[v.status] || v.status}
                </span>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(v.status === 'uploading' || v.status === 'failed') && (
                    <button className="btn btn-sm btn-primary" onClick={() => handleProcess(v.id)}>
                      Обработать
                    </button>
                  )}
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(v.id)}>
                    Удалить
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
