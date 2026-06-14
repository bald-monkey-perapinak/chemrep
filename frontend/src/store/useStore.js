import { create } from 'zustand'
import { api } from '../utils/api'

export const useStore = create((set, get) => ({
  // ── Navigation ────────────────────────────────────────────────────────
  activeSection: 'dashboard',
  setActiveSection: (section) => set({ activeSection: section }),

  // ── Auth state ────────────────────────────────────────────────────────
  isLoggedIn: !!localStorage.getItem('token'),
  setLoggedIn: (v) => set({ isLoggedIn: v }),

  // ── Lessons ───────────────────────────────────────────────────────────
  lessons: [],
  lessonsLoading: false,

  fetchLessons: async () => {
    set({ lessonsLoading: true })
    try {
      const data = await api.listLessons()
      set({ lessons: data || [] })
    } catch { set({ lessons: [] }) }
    set({ lessonsLoading: false })
  },

  addLesson: async (data) => {
    try {
      const lesson = await api.createLesson(data)
      set(s => ({ lessons: [lesson, ...s.lessons] }))
      return lesson
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  deleteLesson: async (id) => {
    try {
      await api.deleteLesson(id)
      set(s => ({ lessons: s.lessons.filter(l => l.id !== id) }))
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  // ── Students ──────────────────────────────────────────────────────────
  students: [],
  studentsLoading: false,

  studentsPage: 1,
  studentsTotal: 0,
  setStudentsPage: (page) => set({ studentsPage: page }),

  fetchStudents: async () => {
    set({ studentsLoading: true })
    try {
      const data = await api.listStudents({ page: get().studentsPage, page_size: 50 })
      set({ students: data?.items || [], studentsTotal: data?.total || 0 })
    } catch { set({ students: [], studentsTotal: 0 }) }
    set({ studentsLoading: false })
  },

  addStudent: async (data) => {
    try {
      const student = await api.createStudent(data)
      set(s => ({ students: [...s.students, student] }))
      return student
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  deleteStudent: async (id) => {
    try {
      await api.deleteStudent(id)
      set(s => ({ students: s.students.filter(st => st.id !== id) }))
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  // ── Knowledge base ────────────────────────────────────────────────────
  kbTree: [],
  kbLoading: false,
  selectedKbNode: null,
  setSelectedKbNode: (id) => set({ selectedKbNode: id }),

  fetchKbTree: async () => {
    set({ kbLoading: true })
    try {
      const fullTree = await api.getFullTree()
      const tree = (fullTree || []).map(cls => ({
        id: cls.id,
        type: 'folder',
        name: cls.name,
        children: (cls.sections || []).map(sec => ({
          id: sec.id,
          type: 'folder',
          name: sec.name,
          children: (sec.topics || []).map(top => ({
            id: top.id,
            type: 'topic',
            name: top.name,
            lesson_script: top.lesson_script || [],
            files: (top.files || []).map(f => ({
              id: f.id,
              name: f.original_name,
              size: f.size_bytes
                ? f.size_bytes > 1048576
                  ? (f.size_bytes / 1048576).toFixed(1) + ' МБ'
                  : Math.round(f.size_bytes / 1024) + ' КБ'
                : '—',
              date: f.uploaded_at
                ? new Date(f.uploaded_at).toLocaleDateString('ru')
                : '—',
            })),
          })),
        })),
      }))
      set({ kbTree: tree })
    } catch {
      set({ kbTree: [] })
    }
    set({ kbLoading: false })
  },

  addRootFolder: async (name) => {
    try {
      const cls = await api.createClass({ name })
      set(s => ({ kbTree: [...s.kbTree, { id: cls.id, type: 'folder', name: cls.name, children: [] }] }))
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  addChildNode: async (parentId, name, type) => {
    const tree = get().kbTree
    const parent = findNode(tree, parentId)
    if (!parent) return

    const isRoot = tree.some(n => n.id === parentId)

    try {
      if (isRoot) {
        // Корневой элемент — создаём секцию (подпапку)
        const sec = await api.createSection(parentId, { name })
        const newNode = { id: sec.id, type: 'folder', name: sec.name, children: [] }
        set(s => ({ kbTree: addChild(s.kbTree, parentId, newNode) }))
      } else {
        // Не корневой — создаём тему
        const topic = await api.createTopic(parentId, { name })
        const newNode = { id: topic.id, type: 'topic', name: topic.name, files: [] }
        set(s => ({ kbTree: addChild(s.kbTree, parentId, newNode) }))
      }
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  renameNode: async (id, name) => {
    const tree = get().kbTree
    const isRoot = tree.some(n => n.id === id)
    try {
      if (isRoot) {
        await api.updateClass(id, { name })
      } else {
        const parent = findParent(tree, id)
        if (parent) {
          const isGrandRoot = tree.some(n => n.id === parent.id)
          if (isGrandRoot) {
            await api.updateSection(id, { name })
          } else {
            await api.updateTopic(id, { name })
          }
        }
      }
      set(s => ({ kbTree: updateNodeName(s.kbTree, id, name) }))
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  deleteNode: async (id) => {
    const tree = get().kbTree
    const isRoot = tree.some(n => n.id === id)
    try {
      if (isRoot) {
        await api.deleteClass(id)
      } else {
        const parent = findParent(tree, id)
        if (parent) {
          const isGrandRoot = tree.some(n => n.id === parent.id)
          if (isGrandRoot) {
            await api.deleteSection(id)
          } else {
            await api.deleteTopic(id)
          }
        }
      }
      set(s => ({
        kbTree: removeNode(s.kbTree, id),
        selectedKbNode: s.selectedKbNode === id ? null : s.selectedKbNode,
      }))
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  addFiles: async (topicId, files) => {
    try {
      await api.uploadFiles(topicId, files)
      await get().fetchKbTree()
      get().showToast('Файлы загружены')
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  deleteFile: async (topicId, fileId) => {
    try {
      await api.deleteFile(fileId)
      set(s => ({
        kbTree: removeFileFromNode(s.kbTree, topicId, fileId),
      }))
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  updateTopic: async (topicId, data) => {
    try {
      await api.updateTopic(topicId, data)
      set(s => ({ kbTree: updateNodeFields(s.kbTree, topicId, data) }))
    } catch (e) {
      get().showToast('Ошибка: ' + e.message)
    }
  },

  // ── Toast ─────────────────────────────────────────────────────────────
  toast: null,
  _showToastTimer: null,
  showToast: (msg) => {
    const prev = get()._showToastTimer
    if (prev) clearTimeout(prev)
    const timer = setTimeout(() => set({ toast: null, _showToastTimer: null }), 2500)
    set({ toast: msg, _showToastTimer: timer })
  },
}))

// ── Tree helpers ──────────────────────────────────────────────────────────

function findNode(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n
    if (n.children) {
      const found = findNode(n.children, id)
      if (found) return found
    }
  }
  return null
}

function findParent(nodes, childId, parent = null) {
  for (const n of nodes) {
    if (n.id === childId) return parent
    if (n.children) {
      const found = findParent(n.children, childId, n)
      if (found) return found
    }
  }
  return null
}

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

function removeFileFromNode(nodes, topicId, fileId) {
  return nodes.map(n => {
    if (n.id === topicId) return { ...n, files: (n.files || []).filter(f => f.id !== fileId) }
    if (n.children) return { ...n, children: removeFileFromNode(n.children, topicId, fileId) }
    return n
  })
}

function updateNodeFields(nodes, nodeId, fields) {
  return nodes.map(n => {
    if (n.id === nodeId) return { ...n, ...fields }
    if (n.children) return { ...n, children: updateNodeFields(n.children, nodeId, fields) }
    return n
  })
}
