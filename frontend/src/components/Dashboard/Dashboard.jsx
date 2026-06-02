import { useStore } from '../../store/useStore'
import { fmtDate } from '../../utils/helpers'

export default function Dashboard() {
  const lessons = useStore((s) => s.lessons)
  const kbTree = useStore((s) => s.kbTree)

  const today = new Date().toISOString().slice(0, 10)
  const todayLessons = lessons.filter((l) => l.date === today)
  const weekStart = new Date()
  weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1)
  const weekEnd = new Date(weekStart)
  weekEnd.setDate(weekEnd.getDate() + 6)
  const weekLessons = lessons.filter((l) => l.date >= weekStart.toISOString().slice(0, 10) && l.date <= weekEnd.toISOString().slice(0, 10))

  const students = new Set(lessons.map((l) => l.student)).size

  function countTopics(nodes) {
    let count = 0
    for (const n of nodes) {
      if (n.type === 'topic') count++
      if (n.children) count += countTopics(n.children)
    }
    return count
  }
  const topicsCount = countTopics(kbTree)

  const upcoming = lessons
    .filter((l) => l.date >= today && l.status !== 'done')
    .sort((a, b) => (a.date + a.time > b.date + b.time ? 1 : -1))
    .slice(0, 5)

  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Занятий сегодня</div>
          <div className="stat-value">{todayLessons.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">На этой неделе</div>
          <div className="stat-value">{weekLessons.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Учеников</div>
          <div className="stat-value">{students}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Тем в базе</div>
          <div className="stat-value">{topicsCount}</div>
        </div>
      </div>

      <div className="card">
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
          <i className="ti ti-calendar-event"></i> Ближайшие занятия
        </div>
        <div className="upcoming-list">
          {upcoming.length === 0 ? (
            <div className="empty-state">
              <i className="ti ti-calendar-off"></i>
              Нет предстоящих занятий
            </div>
          ) : (
            upcoming.map((l) => (
              <div className="lesson-row" key={l.id}>
                <span className="lesson-time">
                  {fmtDate(l.date)}<br />{l.time}
                </span>
                <div className="lesson-info">
                  <div className="lesson-name">{l.student}</div>
                  <div className="lesson-topic">{l.topic}</div>
                </div>
                <span className={`badge ${l.platform === 'zoom' ? 'badge-zoom' : 'badge-ya'}`}>
                  {l.platform === 'zoom' ? 'Zoom' : 'Телемост'}
                </span>
                <a href={l.link} className="btn btn-sm" target="_blank" rel="noreferrer">
                  <i className="ti ti-external-link"></i> Открыть
                </a>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
