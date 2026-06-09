import { useEffect, useState } from 'react'
import { useStore } from './store/useStore'
import Dashboard from './components/Dashboard/Dashboard'
import Calendar from './components/Calendar/Calendar'
import Lessons from './components/Lessons/Lessons'
import KnowledgeBase from './components/KnowledgeBase/KnowledgeBase'
import Students from './components/Students/Students'
import Settings from './pages/Settings'
import LoginPage from './pages/LoginPage'
import NewLessonModal from './components/shared/NewLessonModal'
import LessonMonitor from './components/shared/LessonMonitor'
import Toast from './components/shared/Toast'

const SECTIONS = [
  { id: 'dashboard', label: 'Обзор',      icon: 'ti-layout-dashboard' },
  { id: 'calendar',  label: 'Календарь',  icon: 'ti-calendar' },
  { id: 'lessons',   label: 'Занятия',    icon: 'ti-book' },
  { id: 'students',  label: 'Ученики',    icon: 'ti-users' },
  { id: 'knowledge', label: 'База знаний', icon: 'ti-folder' },
  { id: 'settings',  label: 'Настройки',  icon: 'ti-settings' },
]

export default function App() {
  const teacher          = useStore(s => s.teacher)
  const authReady        = useStore(s => s.authReady)
  const initAuth         = useStore(s => s.initAuth)
  const logout           = useStore(s => s.logout)
  const activeSection    = useStore(s => s.activeSection)
  const setActiveSection = useStore(s => s.setActiveSection)

  const [lessonModalOpen, setLessonModalOpen] = useState(false)
  const [lessonModalDate, setLessonModalDate] = useState(null)
  const [monitorLessonId, setMonitorLessonId] = useState(null)

  useEffect(() => { initAuth() }, [])
  useEffect(() => { window.__openMonitor = setMonitorLessonId }, [setMonitorLessonId])

  function openNewLesson(date) {
    setLessonModalDate(date || null)
    setLessonModalOpen(true)
  }

  if (!authReady) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: 'var(--color-bg)' }}>
        <span style={{ color: 'var(--color-text-muted)', fontSize: 14 }}>Загрузка…</span>
      </div>
    )
  }

  if (!teacher) {
    return <LoginPage onLogin={() => initAuth()} />
  }

  const sectionTitle = SECTIONS.find(s => s.id === activeSection)?.label || ''

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-title">ХимТьютор</div>
          <div className="logo-sub">Кабинет преподавателя</div>
        </div>
        <nav className="nav">
          {SECTIONS.map(s => (
            <button key={s.id}
              className={`nav-item${activeSection === s.id ? ' active' : ''}`}
              onClick={() => setActiveSection(s.id)}>
              <i className={`ti ${s.icon}`}></i> {s.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{teacher.full_name.split(' ').slice(0, 2).join(' ')}</span>
          <button className="icon-btn" title="Выйти" onClick={logout}>
            <i className="ti ti-logout" style={{ fontSize: 15 }}></i>
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <span className="topbar-title">{sectionTitle}</span>
          {activeSection !== 'settings' && (
            <button className="btn btn-primary" onClick={() => openNewLesson()}>
              <i className="ti ti-plus"></i> Новое занятие
            </button>
          )}
        </div>
        <div className="content">
          {activeSection === 'dashboard' && <Dashboard />}
          {activeSection === 'calendar'  && <Calendar onOpenNewLesson={openNewLesson} />}
          {activeSection === 'lessons'   && <Lessons />}
          {activeSection === 'students'  && <Students />}
          {activeSection === 'knowledge' && <KnowledgeBase />}
          {activeSection === 'settings'  && <Settings />}
        </div>
      </main>

      {lessonModalOpen && (
        <NewLessonModal
          onClose={() => setLessonModalOpen(false)}
          defaultDate={lessonModalDate}
        />
      )}
      <Toast />
      {monitorLessonId && (
        <LessonMonitor
          lessonId={monitorLessonId}
          onClose={() => setMonitorLessonId(null)}
        />
      )}
    </div>
  )
}
