import { useState } from 'react'
import { useStore } from './store/useStore'
import Dashboard from './components/Dashboard/Dashboard'
import Calendar from './components/Calendar/Calendar'
import Lessons from './components/Lessons/Lessons'
import KnowledgeBase from './components/KnowledgeBase/KnowledgeBase'
import NewLessonModal from './components/shared/NewLessonModal'
import Toast from './components/shared/Toast'

const SECTIONS = [
  { id: 'dashboard', label: 'Обзор', icon: 'ti-layout-dashboard' },
  { id: 'calendar', label: 'Календарь', icon: 'ti-calendar' },
  { id: 'lessons', label: 'Занятия', icon: 'ti-book' },
  { id: 'knowledge', label: 'База знаний', icon: 'ti-folder' },
]

export default function App() {
  const activeSection = useStore((s) => s.activeSection)
  const setActiveSection = useStore((s) => s.setActiveSection)
  const [lessonModalOpen, setLessonModalOpen] = useState(false)
  const [lessonModalDate, setLessonModalDate] = useState(null)

  function openNewLesson(date) {
    setLessonModalDate(date || null)
    setLessonModalOpen(true)
  }

  const sectionTitle = SECTIONS.find((s) => s.id === activeSection)?.label || ''

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-sub">Кабинет преподавателя</div>
        </div>
        <nav className="nav">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              className={`nav-item${activeSection === s.id ? ' active' : ''}`}
              onClick={() => setActiveSection(s.id)}
            >
              <i className={`ti ${s.icon}`}></i> {s.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">Иванова А.П.</div>
      </aside>

      <main className="main">
        <div className="topbar">
          <span className="topbar-title">{sectionTitle}</span>
          <button className="btn btn-primary" onClick={() => openNewLesson()}>
            <i className="ti ti-plus"></i> Новое занятие
          </button>
        </div>
        <div className="content">
          {activeSection === 'dashboard' && <Dashboard />}
          {activeSection === 'calendar' && <Calendar onOpenNewLesson={openNewLesson} />}
          {activeSection === 'lessons' && <Lessons />}
          {activeSection === 'knowledge' && <KnowledgeBase />}
        </div>
      </main>

      {lessonModalOpen && (
        <NewLessonModal
          onClose={() => setLessonModalOpen(false)}
          defaultDate={lessonModalDate}
        />
      )}

      <Toast />
    </div>
  )
}
