import { lazy, Suspense, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { useStore } from './store/useStore'
import { api } from './utils/api'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import Toast from './components/shared/Toast'
import ErrorBoundary from './components/shared/ErrorBoundary'
import NotFound from './components/shared/NotFound'
import { useOffline } from './hooks/useOffline'

const Dashboard    = lazy(() => import('./components/Dashboard/Dashboard'))
const Calendar     = lazy(() => import('./components/Calendar/Calendar'))
const Lessons      = lazy(() => import('./components/Lessons/Lessons'))
const Students     = lazy(() => import('./components/Students/Students'))
const KnowledgeBase = lazy(() => import('./components/KnowledgeBase/KnowledgeBase'))
const Settings     = lazy(() => import('./pages/Settings'))
const NewLessonModal = lazy(() => import('./components/shared/NewLessonModal'))
const LessonMonitor  = lazy(() => import('./components/shared/LessonMonitor'))

const SECTIONS = [
  { id: 'dashboard', label: 'Обзор',       path: '/' },
  { id: 'calendar',  label: 'Календарь',   path: '/calendar' },
  { id: 'lessons',   label: 'Занятия',     path: '/lessons' },
  { id: 'students',  label: 'Ученики',     path: '/students' },
  { id: 'knowledge', label: 'База знаний', path: '/knowledge' },
  { id: 'settings',  label: 'Настройки',  path: '/settings' },
]

function Loading() {
  return <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-text-muted)' }}>Загрузка...</div>
}

function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()
  const fetchStudents = useStore(s => s.fetchStudents)
  const fetchLessons  = useStore(s => s.fetchLessons)
  const fetchKbTree   = useStore(s => s.fetchKbTree)

  const [lessonModalOpen, setLessonModalOpen] = useState(false)
  const [lessonModalDate, setLessonModalDate] = useState(null)
  const [monitorLessonId, setMonitorLessonId] = useState(null)

  const isOffline = useOffline()

  useEffect(() => {
    fetchStudents()
    fetchLessons()
    fetchKbTree()
  }, [])

  useEffect(() => { window.__openMonitor = setMonitorLessonId }, [])

  const activeSection = SECTIONS.find(s => s.path === location.pathname)?.id || 'dashboard'

  function openNewLesson(date) {
    setLessonModalDate(date || null)
    setLessonModalOpen(true)
  }

  function handleNav(path) {
    navigate(path)
  }

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
              onClick={() => handleNav(s.path)}>
              {s.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="link-btn" style={{ fontSize: 12 }}
            onClick={() => { api.logout(); window.dispatchEvent(new Event('auth:logout')); navigate('/login') }}>
            Выйти
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <span className="topbar-title">
            {SECTIONS.find(s => s.id === activeSection)?.label || ''}
          </span>
          {activeSection !== 'settings' && (
            <button className="btn btn-primary" onClick={() => openNewLesson()}>
              Новое занятие
            </button>
          )}
        </div>
        {isOffline && (
          <div style={{
            background: 'var(--color-warning)',
            color: 'white',
            padding: '8px 16px',
            textAlign: 'center'
          }}>
            Нет подключения к интернету
          </div>
        )}
        <div className="content">
          <ErrorBoundary>
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/calendar" element={<Calendar onOpenNewLesson={openNewLesson} />} />
                <Route path="/lessons" element={<Lessons />} />
                <Route path="/students" element={<Students />} />
                <Route path="/knowledge" element={<KnowledgeBase />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
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

export default function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem('token'))
  const [authChecking, setAuthChecking] = useState(!!localStorage.getItem('token'))

  useEffect(() => {
    if (!localStorage.getItem('token')) return
    api.me()
      .then(() => setLoggedIn(true))
      .catch(() => { localStorage.removeItem('token'); setLoggedIn(false) })
      .finally(() => setAuthChecking(false))
  }, [])

  useEffect(() => {
    const handleLogout = () => setLoggedIn(false)
    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [])

  if (authChecking) return null

  return (
    <BrowserRouter>
      <Routes>
        {!loggedIn ? (
          <>
            <Route path="/register" element={<RegisterPage onRegister={() => setLoggedIn(true)} />} />
            <Route path="*" element={<LoginPage onLogin={() => setLoggedIn(true)} />} />
          </>
        ) : (
          <>
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/*" element={<AppShell />} />
          </>
        )}
      </Routes>
    </BrowserRouter>
  )
}
