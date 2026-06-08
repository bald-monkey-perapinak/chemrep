import { create } from 'zustand'
import { api } from '../utils/api'

export const useStore = create((set, get) => ({
  // ── Auth ──────────────────────────────────────────────────────────────
  teacher:    null,
  authReady:  false,
  setTeacher: (teacher) => set({ teacher }),

  initAuth: async () => {
    const token = localStorage.getItem('token')
    if (!token) { set({ authReady: true }); return }
    try {
      const teacher = await api.me()
      set({ teacher, authReady: true })
      get().fetchAll()
    } catch {
      localStorage.removeItem('token')
      set({ authReady: true })
    }
  },

  logout: () => {
    api.logout()
    set({ teacher: null, lessons: [], students: [] })
  },

  // ── Navigation ────────────────────────────────────────────────────────
  activeSection: 'dashboard',
  setActiveSection: (section) => set({ activeSection: section }),

  // ── Lessons ───────────────────────────────────────────────────────────
  lessons:       [],
  lessonsLoading: false,

  fetchLessons: async () => {
    set({ lessonsLoading: true })
    try {
      const lessons = await api.listLessons({ limit: 100 })
      set({ lessons })
    } catch (e) {
      console.error('fetchLessons:', e)
    } finally {
      set({ lessonsLoading: false })
    }
  },

  addLesson: async (data) => {
    const lesson = await api.createLesson(data)
    set(s => ({ lessons: [lesson, ...s.lessons] }))
    return lesson
  },

  deleteLesson: async (id) => {
    await api.deleteLesson(id)
    set(s => ({ lessons: s.lessons.filter(l => l.id !== id) }))
  },

  // ── Students ──────────────────────────────────────────────────────────
  students:       [],
  studentsLoading: false,

  fetchStudents: async () => {
    set({ studentsLoading: true })
    try {
      const students = await api.listStudents()
      set({ students })
    } catch (e) {
      console.error('fetchStudents:', e)
    } finally {
      set({ studentsLoading: false })
    }
  },

  addStudent: async (data) => {
    const student = await api.createStudent(data)
    set(s => ({ students: [student, ...s.students] }))
    return student
  },

  deleteStudent: async (id) => {
    await api.deleteStudent(id)
    set(s => ({ students: s.students.filter(s => s.id !== id) }))
  },

  // ── Knowledge base (tree managed via API) ────────────────────────────
  kbTree:        [],
  kbLoading:     false,
  selectedKbNode: null,
  setSelectedKbNode: (id) => set({ selectedKbNode: id }),

  fetchKbTree: async () => {
    set({ kbLoading: true })
    try {
      const classes = await api.listClasses()
      // Build local tree from classes (sections loaded on demand)
      const tree = classes.map(c => ({
        id: c.id, type: 'folder', name: c.name,
        children: (c.sections || []).map(s => ({
          id: s.id, type: 'folder', name: s.name, children: [],
        })),
      }))
      set({ kbTree: tree })
    } catch (e) {
      console.error('fetchKbTree:', e)
    } finally {
      set({ kbLoading: false })
    }
  },

  addRootFolder: async (name) => {
    const cls = await api.createClass({ name, sort_order: 0 })
    set(s => ({ kbTree: [...s.kbTree, { id: cls.id, type: 'folder', name: cls.name, children: [] }] }))
  },

  renameNode: async (id, name) => {
    // Try class rename first, then section, then topic
    for (const fn of [
      () => api.updateClass(id, { name }),
      () => api.updateSection(id, { name }),
      () => api.updateTopic(id, { name }),
    ]) {
      try { await fn(); break } catch {}
    }
    set(s => ({
      kbTree: updateNodeName(s.kbTree, id, name),
    }))
  },

  deleteNode: async (id) => {
    for (const fn of [
      () => api.deleteClass(id),
      () => api.deleteSection(id),
      () => api.deleteTopic(id),
    ]) {
      try { await fn(); break } catch {}
    }
    set(s => ({
      kbTree: removeNode(s.kbTree, id),
      selectedKbNode: s.selectedKbNode === id ? null : s.selectedKbNode,
    }))
  },

  addChildNode: async (parentId, name, type) => {
    let newNode
    if (type === 'folder') {
      const sec = await api.createSection(parentId, { name, sort_order: 0 })
        .catch(() => null)
      if (sec) {
        newNode = { id: sec.id, type: 'folder', name: sec.name, children: [] }
      }
    } else {
      const topic = await api.createTopic(parentId, { name, sort_order: 0 })
        .catch(() => null)
      if (topic) {
        newNode = { id: topic.id, type: 'topic', name: topic.name, files: [] }
      }
    }
    if (!newNode) return
    set(s => ({ kbTree: addChild(s.kbTree, parentId, newNode) }))
  },

  addFiles: async (topicId, files) => {
    const result = await api.uploadFiles(topicId, files)
    const newFiles = (result.uploaded || []).map(f => ({
      id: f.id, name: f.original_name,
      size: f.size_bytes ? Math.round(f.size_bytes / 1024) + ' КБ' : '—',
      date: new Date(f.uploaded_at).toLocaleDateString('ru'),
    }))
    set(s => ({ kbTree: addFilesToNode(s.kbTree, topicId, newFiles) }))
  },

  deleteFile: async (topicId, fileId) => {
    await api.deleteFile(fileId)
    set(s => ({ kbTree: removeFileFromNode(s.kbTree, topicId, fileId) }))
  },

  fetchAll: () => {
    get().fetchLessons()
    get().fetchStudents()
    get().fetchKbTree()
  },

  // ── Toast ─────────────────────────────────────────────────────────────
  toast: null,
  showToast: (msg) => {
    set({ toast: msg })
    setTimeout(() => set({ toast: null }), 2500)
  },
}))

// ── Tree helpers ──────────────────────────────────────────────────────────

function updateNodeName(nodes, id, name) {
  return nodes.map(n => {
    if (n.id === id) return { ...n, name }
    if (n.children) return { ...n, children: updateNodeName(n.children, id, name) }
    return n
  })
}

function removeNode(nodes, id) {
  return nodes
    .filter(n => n.id !== id)
    .map(n => n.children ? { ...n, children: removeNode(n.children, id) } : n)
}

function addChild(nodes, parentId, newNode) {
  return nodes.map(n => {
    if (n.id === parentId) return { ...n, children: [...(n.children || []), newNode] }
    if (n.children) return { ...n, children: addChild(n.children, parentId, newNode) }
    return n
  })
}

function addFilesToNode(nodes, topicId, files) {
  return nodes.map(n => {
    if (n.id === topicId) return { ...n, files: [...(n.files || []), ...files] }
    if (n.children) return { ...n, children: addFilesToNode(n.children, topicId, files) }
    return n
  })
}

function removeFileFromNode(nodes, topicId, fileId) {
  return nodes.map(n => {
    if (n.id === topicId) return { ...n, files: (n.files || []).filter(f => f.id !== fileId) }
    if (n.children) return { ...n, children: removeFileFromNode(n.children, topicId, fileId) }
    return n
  })
}
