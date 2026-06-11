const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

function getToken() {
  return localStorage.getItem('token')
}

async function request(method, path, body) {
  const token = getToken()
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  }
  if (body) opts.body = JSON.stringify(body)

  const res = await fetch(`${BASE}${path}`, opts)

  if (res.status === 401) {
    localStorage.removeItem('token')
    window.location.reload()
    return
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Ошибка сервера')
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────
  login:    async (email, password) => {
    const token = getToken()
    const formBody = new URLSearchParams({ username: email, password }).toString()
    const res = await fetch(`${BASE}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: formBody,
    })
    if (res.status === 401) {
      throw new Error('Неверный email или пароль')
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }))
      throw new Error(err.detail || 'Ошибка сервера')
    }
    const d = await res.json()
    localStorage.setItem('token', d.access_token)
    return d
  },
  register: (email, password, full_name) =>
    request('POST', '/auth/register', { email, password, full_name }),
  me:       ()                => request('GET',  '/auth/me'),
  updateMe: (data)            => request('PATCH', '/auth/me', data),
  logout:   ()                => localStorage.removeItem('token'),

  // ── Lessons ─────────────────────────────────────────────────────────────
  listLessons:   (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null))
    ).toString()
    return request('GET', `/lessons${qs ? '?' + qs : ''}`)
  },
  createLesson:  (data)       => request('POST',   '/lessons', data),
  getLesson:     (id)         => request('GET',    `/lessons/${id}`),
  updateLesson:  (id, data)   => request('PATCH',  `/lessons/${id}`, data),
  deleteLesson:  (id)         => request('DELETE', `/lessons/${id}`),
  getLessonSession: (id)      => request('GET',    `/lessons/${id}/session`),
  upsertHomework: (id, data)  => request('PATCH',  `/lessons/${id}/homework`, data),

  // ── Students ────────────────────────────────────────────────────────────
  listStudents:  ()           => request('GET',    '/students'),
  createStudent: (data)       => request('POST',   '/students', data),
  getStudent:    (id)         => request('GET',    `/students/${id}`),
  updateStudent: (id, data)   => request('PATCH',  `/students/${id}`, data),
  deleteStudent: (id)         => request('DELETE', `/students/${id}`),

  // ── Knowledge ───────────────────────────────────────────────────────────
  listClasses:     ()              => request('GET',    '/knowledge/classes'),
  createClass:     (data)          => request('POST',   '/knowledge/classes', data),
  updateClass:     (id, data)      => request('PATCH',  `/knowledge/classes/${id}`, data),
  deleteClass:     (id)            => request('DELETE', `/knowledge/classes/${id}`),
  getClassTree:    (id)            => request('GET',    `/knowledge/classes/${id}/tree`),
  createSection:   (cid, data)     => request('POST',   `/knowledge/classes/${cid}/sections`, data),
  updateSection:   (id, data)      => request('PATCH',  `/knowledge/sections/${id}`, data),
  deleteSection:   (id)            => request('DELETE', `/knowledge/sections/${id}`),
  listTopics:      (sid)           => request('GET',    `/knowledge/sections/${sid}/topics`),
  createTopic:     (sid, data)     => request('POST',   `/knowledge/sections/${sid}/topics`, data),
  getTopic:        (id)            => request('GET',    `/knowledge/topics/${id}`),
  updateTopic:     (id, data)      => request('PATCH',  `/knowledge/topics/${id}`, data),
  deleteTopic:     (id)            => request('DELETE', `/knowledge/topics/${id}`),
  searchKnowledge: (q)             => request('GET',    `/knowledge/search?q=${encodeURIComponent(q)}`),

  uploadFiles: async (topicId, files, role = 'material') => {
    const token = getToken()
    const form  = new FormData()
    files.forEach(f => form.append('files', f))
    const res = await fetch(`${BASE}/knowledge/topics/${topicId}/files?file_role=${role}`, {
      method:  'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body:    form,
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Upload failed')
    return res.json()
  },

  deleteFile: (id) => request('DELETE', `/knowledge/files/${id}`),

  // ── Sessions ────────────────────────────────────────────────────────────
  getSession:    (lessonId) => request('GET', `/sessions/${lessonId}`),
  getTranscript: (lessonId) => request('GET', `/sessions/${lessonId}/transcript`),
  getDialog:     (lessonId) => request('GET', `/sessions/${lessonId}/dialog`),

  // ── Voice ───────────────────────────────────────────────────────────────
  voiceStatus: ()         => request('GET',    '/voice/status'),
  deleteVoice: ()         => request('DELETE', '/voice'),
  cloneVoice: async (files) => {
    const token = getToken()
    const form  = new FormData()
    files.forEach(f => form.append('files', f))
    const res = await fetch(`${BASE}/voice/clone`, {
      method:  'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body:    form,
    })
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Clone failed')
    return res.json()
  },
}
