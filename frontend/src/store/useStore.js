import { create } from 'zustand'

// Начальные данные для работы без бэкенда
const initialLessons = [
  { id: '1', student_name: 'Петров Михаил', scheduled_at: new Date().toISOString(), topic_name: 'Алканы — строение', vcs_platform: 'zoom', vcs_link: 'https://zoom.us/j/123456', status: 'scheduled' },
  { id: '2', student_name: 'Сидорова Анна', scheduled_at: new Date(Date.now() + 3600000).toISOString(), topic_name: 'Степени окисления', vcs_platform: 'yandex', vcs_link: 'https://telemost.yandex.ru/j/abc', status: 'scheduled' },
]

const initialStudents = [
  { id: '1', full_name: 'Петров Михаил', email: 'petrov@mail.ru', grade: 10 },
  { id: '2', full_name: 'Сидорова Анна', email: 'sidorova@mail.ru', grade: 9 },
]

const initialKbTree = [
  {
    id: 'c10', type: 'folder', name: '10 класс', children: [
      { id: 'c10-org', type: 'folder', name: 'Органическая химия', children: [
        { id: 'c10-alk', type: 'topic', name: 'Алканы', files: [
          { id: 'f1', name: 'Алканы_конспект.pdf', size: '1.5 МБ', date: '01.06.2026' },
        ]},
        { id: 'c10-alk2', type: 'topic', name: 'Алкены', files: [] },
      ]},
    ],
  },
  {
    id: 'c9', type: 'folder', name: '9 класс', children: [
      { id: 'c9-r', type: 'folder', name: 'Типы реакций', children: [
        { id: 'c9-r1', type: 'topic', name: 'Реакции замещения', files: [] },
      ]},
    ],
  },
]

export const useStore = create((set, get) => ({
  // ── Navigation ────────────────────────────────────────────────────────
  activeSection: 'dashboard',
  setActiveSection: (section) => set({ activeSection: section }),

  // ── Lessons ───────────────────────────────────────────────────────────
  lessons: initialLessons,
  lessonsLoading: false,

  addLesson: (data) => {
    const lesson = { ...data, id: Date.now().toString(), status: 'scheduled' }
    set(s => ({ lessons: [lesson, ...s.lessons] }))
    return lesson
  },

  deleteLesson: (id) => set(s => ({ lessons: s.lessons.filter(l => l.id !== id) })),

  // ── Students ──────────────────────────────────────────────────────────
  students: initialStudents,
  studentsLoading: false,

  addStudent: (data) => {
    const student = { ...data, id: Date.now().toString(), is_active: true }
    set(s => ({ students: [student, ...s.students] }))
    return student
  },

  deleteStudent: (id) => set(s => ({ students: s.students.filter(s => s.id !== id) })),

  // ── Knowledge base ────────────────────────────────────────────────────
  kbTree: initialKbTree,
  kbLoading: false,
  selectedKbNode: null,
  setSelectedKbNode: (id) => set({ selectedKbNode: id }),

  addRootFolder: (name) => set(s => ({
    kbTree: [...s.kbTree, { id: 'f_' + Date.now(), type: 'folder', name, children: [] }],
  })),

  addChildNode: (parentId, name, type) => {
    const newNode = type === 'topic'
      ? { id: 'n_' + Date.now(), type: 'topic', name, files: [] }
      : { id: 'n_' + Date.now(), type: 'folder', name, children: [] }
    set(s => ({ kbTree: addChild(s.kbTree, parentId, newNode) }))
  },

  renameNode: (id, name) => set(s => ({
    kbTree: updateNodeName(s.kbTree, id, name),
  })),

  deleteNode: (id) => set(s => ({
    kbTree: removeNode(s.kbTree, id),
    selectedKbNode: s.selectedKbNode === id ? null : s.selectedKbNode,
  })),

  addFiles: (topicId, files) => {
    const newFiles = Array.from(files).map(f => ({
      id: 'file_' + Date.now() + '_' + f.name,
      name: f.name,
      size: f.size > 1048576 ? (f.size / 1048576).toFixed(1) + ' МБ' : Math.round(f.size / 1024) + ' КБ',
      date: new Date().toLocaleDateString('ru'),
    }))
    set(s => ({ kbTree: addFilesToNode(s.kbTree, topicId, newFiles) }))
  },

  deleteFile: (topicId, fileId) => set(s => ({
    kbTree: removeFileFromNode(s.kbTree, topicId, fileId),
  })),

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
