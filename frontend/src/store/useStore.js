import { create } from 'zustand'

const initialLessons = [
  { id: 1, student: 'Петров Михаил', date: '2026-06-02', time: '16:00', topic: 'Алканы — строение', platform: 'zoom', link: 'https://zoom.us/j/123456', status: 'upcoming' },
  { id: 2, student: 'Сидорова Анна', date: '2026-06-02', time: '18:30', topic: 'Степени окисления', platform: 'ya', link: 'https://telemost.yandex.ru/j/abc', status: 'upcoming' },
  { id: 3, student: 'Козлов Дмитрий', date: '2026-06-03', time: '15:00', topic: 'Реакции замещения', platform: 'zoom', link: 'https://zoom.us/j/789', status: 'upcoming' },
  { id: 4, student: 'Новикова Елена', date: '2026-05-28', time: '17:00', topic: 'Периодический закон', platform: 'zoom', link: 'https://zoom.us/j/555', status: 'done' },
]

const initialKbTree = [
  {
    id: 'c8', type: 'class', name: '8 класс', children: [
      { id: 'c8-org', type: 'section', name: 'Основные понятия', children: [
        { id: 'c8-org-1', type: 'topic', name: 'Атом и молекула', files: [
          { name: 'Конспект_атом.pdf', size: '1.2 МБ', date: '15.05.2026' },
          { name: 'Схема_строения.png', size: '340 КБ', date: '15.05.2026' },
        ]},
      ]},
    ],
  },
  {
    id: 'c9', type: 'class', name: '9 класс', children: [
      { id: 'c9-reac', type: 'section', name: 'Типы реакций', children: [
        { id: 'c9-reac-1', type: 'topic', name: 'Реакции замещения', files: [
          { name: 'Конспект_замещение.pdf', size: '890 КБ', date: '10.05.2026' },
        ]},
        { id: 'c9-reac-2', type: 'topic', name: 'Реакции обмена', files: [] },
      ]},
    ],
  },
  {
    id: 'c10', type: 'class', name: '10 класс', children: [
      { id: 'c10-org', type: 'section', name: 'Органическая химия', children: [
        { id: 'c10-org-alk', type: 'topic', name: 'Алканы', files: [
          { name: 'Алканы_конспект.pdf', size: '1.5 МБ', date: '01.06.2026' },
          { name: 'Таблица_свойств.xlsx', size: '220 КБ', date: '01.06.2026' },
          { name: 'Домашнее_задание.pdf', size: '500 КБ', date: '01.06.2026' },
        ]},
        { id: 'c10-org-alk2', type: 'topic', name: 'Алкены', files: [] },
      ]},
    ],
  },
]

const initialCustomFolders = [
  { id: 'cf1', name: 'Подготовка к ОГЭ', icon: 'ti-folder', count: 7 },
  { id: 'cf2', name: 'Олимпиадные задачи', icon: 'ti-folder', count: 3 },
]

export const useStore = create((set, get) => ({
  // Navigation
  activeSection: 'dashboard',
  setActiveSection: (section) => set({ activeSection: section }),

  // Lessons
  lessons: initialLessons,
  addLesson: (lesson) => set((state) => ({ lessons: [...state.lessons, { ...lesson, id: Date.now() }] })),
  deleteLesson: (id) => set((state) => ({ lessons: state.lessons.filter((l) => l.id !== id) })),

  // Knowledge base tree
  kbTree: initialKbTree,
  selectedKbNode: null,
  setSelectedKbNode: (id) => set({ selectedKbNode: id }),
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
  addSubfolder: (parentId, name) => set((state) => {
    const newNode = { id: 'f_' + Date.now(), type: 'section', name, children: [] }
    const updateTree = (nodes) => nodes.map((n) => {
      if (n.id === parentId) return { ...n, children: [...(n.children || []), newNode] }
      if (n.children) return { ...n, children: updateTree(n.children) }
      return n
    })
    return { kbTree: updateTree(state.kbTree) }
  }),

  // Custom folders
  customFolders: initialCustomFolders,
  addCustomFolder: (name) => set((state) => ({
    customFolders: [...state.customFolders, { id: 'cf' + Date.now(), name, icon: 'ti-folder', count: 0 }],
  })),
  renameCustomFolder: (id, name) => set((state) => ({
    customFolders: state.customFolders.map((f) => f.id === id ? { ...f, name } : f),
  })),
  deleteCustomFolder: (id) => set((state) => ({
    customFolders: state.customFolders.filter((f) => f.id !== id),
  })),

  // Toast
  toast: null,
  showToast: (msg) => {
    set({ toast: msg })
    setTimeout(() => set({ toast: null }), 2500)
  },
}))

export const SYSTEM_FOLDERS = [
  { id: 'c8',  name: '8 класс',  icon: 'ti-school', count: 12 },
  { id: 'c9',  name: '9 класс',  icon: 'ti-school', count: 18 },
  { id: 'c10', name: '10 класс', icon: 'ti-school', count: 24 },
  { id: 'c11', name: '11 класс', icon: 'ti-school', count: 15 },
]
