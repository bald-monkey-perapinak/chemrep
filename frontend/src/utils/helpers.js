export function fmtDate(d) {
  const [, m, day] = d.split('-')
  const mo = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
  return `${parseInt(day)} ${mo[parseInt(m) - 1]}`
}

export function plural(n) {
  if (n % 10 === 1 && n % 100 !== 11) return ''
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return 'а'
  return 'ов'
}

export function fileIcon(name) {
  if (name.endsWith('.pdf')) return 'ti-file-type-pdf'
  if (name.endsWith('.xlsx') || name.endsWith('.csv')) return 'ti-file-spreadsheet'
  if (name.endsWith('.png') || name.endsWith('.jpg')) return 'ti-photo'
  return 'ti-file'
}

export function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' Б'
  if (bytes < 1048576) return Math.round(bytes / 1024) + ' КБ'
  return (bytes / 1048576).toFixed(1) + ' МБ'
}

export function findNode(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n
    if (n.children) {
      const found = findNode(n.children, id)
      if (found) return found
    }
  }
  return null
}

export function countChildren(n) {
  if (!n.children) return 0
  return n.children.length + n.children.reduce((s, c) => s + countChildren(c), 0)
}

export function typeLabel(t) {
  return t === 'class' ? 'Класс' : t === 'section' ? 'Раздел' : 'Тема'
}

export const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]
export const DAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
