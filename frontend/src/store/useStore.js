import { create } from 'zustand'

const initialLessons = [
  { id: 1, student: 'Петров Михаил', date: '2026-06-02', time: '16:00', topic: 'Алканы — строение', platform: 'zoom', link: 'https://zoom.us/j/123456', status: 'upcoming' },
  { id: 2, student: 'Сидорова Анна', date: '2026-06-02', time: '18:30', topic: 'Степени окисления', platform: 'ya', link: 'https://telemost.yandex.ru/j/abc', status: 'upcoming' },
  { id: 3, student: 'Козлов Дмитрий', date: '2026-06-03', time: '15:00', topic: 'Реакции замещения', platform: 'zoom', link: 'https://zoom.us/j/789', status: 'upcoming' },
  { id: 4, student: 'Новикова Елена', date: '2026-05-28', time: '17:00', topic: 'Периодический закон', platform: 'zoom', link: 'https://zoom.us/j/555', status: 'done' },
]

const initialKbTree = [
  {
    id: 'c8', type: 'folder', name: '8 класс', children: [
      { id: 'c8-org', type: 'folder', name: 'Основные понятия', children: [
        { id: 'c8-org-1', type: 'topic', name: 'Атом и молекула', files: [
          { name: 'Конспект_атом.pdf', size: '1.2 МБ', date: '15.05.2026' },
          { name: 'Схема_строения.png', size: '340 КБ', date: '15.05.2026' },
        ]},
      ]},
    ],
  },
  {
    id: 'c9', type: 'folder', name: '9 класс', children: [
      { id: 'c9-reac', type: 'folder', name: 'Типы реакций', children: [
        { id: 'c9-reac-1', type: 'topic', name: 'Реакции замещения', files: [
          { name: 'Конспект_замещение.pdf', size: '890 КБ', date: '10.05.2026' },
        ]},
        { id: 'c9-reac-2', type: 'topic', name: 'Реакции обмена', files: [] },
      ]},
    ],
  },
  {
    id: 'c10', type: 'folder', name: '10 класс', children: [
      { id: 'c10-org', type: 'folder', name: 'Органическая химия', children: [
        { id: 'c10-org-alk', type: 'topic', name: 'Алканы', files: [
          { name: 'Алканы_конспект.pdf', size: '1.5 МБ', date: '01.06.2026' },
          { name: 'Таблица_свойств.xlsx', size: '220 КБ', date: '01.06.2026' },
          { name: 'Домашнее_задание.pdf', size: '500 КБ', date: '01.06.2026' },
        ]},
        { id: 'c10-org-alk2', type: 'topic', name: 'Алкены', files: [] },
      ]},
    ],
  },
  { id: 'cf1', type: 'folder', name: 'Подготовка к ОГЭ', children: [] },
  { id: 'cf2', type: 'folder', name: 'Олимпиадные задачи', children: [] },
]

export const useStore = create((set) => ({
  // Navigation
  activeSection: 'dashboard',
  setActiveSection: (section) => set({ activeSection: section }),

  // Lessons
  lessons: initialLessons,
  addLesson: (lesson) => set((state) => ({ lessons: [...state.lessons, { ...lesson, id: Date.now() }] })),
  deleteLesson: (id) => set((state) => ({ lessons: state.lessons.filter((l) => l.id !== id) })),

  // Knowledge base tree (single unified tree, user owns everything)
  kbTree: initialKbTree,
  selectedKbNode: null,
  setSelectedKbNode: (id) => set({ selectedKbNode: id }),

  addRootFolder: (name) => set((state) => ({
    kbTree: [...state.kbTree, { id: 'f_' + Date.now(), type: 'folder', name, children: [] }],
  })),

  addChildNode: (parentId, name, type) => set((state) => {
    const newNode = type === 'topic'
      ? { id: 'n_' + Date.now(), type: 'topic', name, files: [] }
      : { id: 'n_' + Date.now(), type: 'folder', name, children: [] }
    const updateTree = (nodes) => nodes.map((n) => {
      if (n.id === parentId) return { ...n, children: [...(n.children || []), newNode] }
      if (n.children) return { ...n, children: updateTree(n.children) }
      return n
    })
    return { kbTree: updateTree(state.kbTree) }
  }),

  renameNode: (id, name) => set((state) => {
    const updateTree = (nodes) => nodes.map((n) => {
      if (n.id === id) return { ...n, name }
      if (n.children) return { ...n, children: updateTree(n.children) }
      return n
    })
    return { kbTree: updateTree(state.kbTree) }
  }),

  deleteNode: (id) => set((state) => {
    const removeFrom = (nodes) => nodes
      .filter((n) => n.id !== id)
      .map((n) => n.children ? { ...n, children: removeFrom(n.children) } : n)
    return { kbTree: removeFrom(state.kbTree), selectedKbNode: state.selectedKbNode === id ? null : state.selectedKbNode }
  }),

  deleteFile: (topicId, fileName) => set((state) => {
    const updateTree = (nodes) => nodes.map((n) => {
      if (n.id === topicId) return { ...n, files: n.files.filter((f) => f.name !== fileName) }
      if (n.children) return { ...n, children: updateTree(n.children) }
      return n
    })
    return { kbTree: updateTree(state.kbTree) }
  }),

  addFiles: (topicId, files) => set((state) => {
    const updateTree = (nodes) => nodes.map((n) => {
      if (n.id === topicId) return { ...n, files: [...(n.files || []), ...files] }
      if (n.children) return { ...n, children: updateTree(n.children) }
      return n
    })
    return { kbTree: updateTree(state.kbTree) }
  }),

  // Toast
  toast: null,
  showToast: (msg) => {
    set({ toast: msg })
    setTimeout(() => set({ toast: null }), 2500)
  },
}))
