import { useStore } from '../../store/useStore'

export default function Dashboard() {
  const lessons  = useStore(s => s.lessons)
  const students = useStore(s => s.students)
  const kbTree   = useStore(s => s.kbTree)

  const today = new Date().toISOString().slice(0, 10)
  const todayLessons = lessons.filter(l => l.scheduled_at?.slice(0, 10) === today)

  const weekStart = new Date(); weekStart.setDate(weekStart.getDate() - weekStart.getDay() + 1)
  const weekEnd   = new Date(weekStart); weekEnd.setDate(weekEnd.getDate() + 6)
  const weekLessons = lessons.filter(l => {
    const d = l.scheduled_at?.slice(0, 10)
    return d >= weekStart.toISOString().slice(0, 10) && d <= weekEnd.toISOString().slice(0, 10)
  })

  function countTopics(nodes) {
    let n = 0
    for (const node of nodes) {
      if (node.type === 'topic') n++
      if (node.children) n += countTopics(node.children)
    }
    return n
  }

  const upcoming = lessons
    .filter(l => l.status === 'scheduled' || l.status === 'in_progress')
    .sort((a, b) => a.scheduled_at > b.scheduled_at ? 1 : -1)
    .slice(0, 5)

  function fmtDt(iso) {
    if (!iso) return '—'
    const d = new Date(iso)
    const mo = ['янв','фев','мар','апр','май','июн','июл','авг','сен','окт','ноя','дек']
    return `${d.getDate()} ${mo[d.getMonth()]}, ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  }

  const statusBadge = {
    scheduled:   { cls: 'badge-upcoming', label: 'Ожидает' },
    in_progress: { cls: 'badge-active',   label: 'Идёт сейчас' },
  }

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
          <div className="stat-value">{students.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Тем в базе</div>
          <div className="stat-value">{countTopics(kbTree)}</div>
        </div>
      </div>

      <div className="card">
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
          <i className="ti ti-calendar-event"></i> Ближайшие занятия
        </div>
        <div className="upcoming-list">
          {upcoming.length === 0 ? (
            <div className="empty-state">
              <i className="ti ti-calendar-off"></i>Нет предстоящих занятий
            </div>
          ) : upcoming.map(l => {
            const badge = statusBadge[l.status] || {}
            return (
              <div className="lesson-row" key={l.id}>
                <span className="lesson-time">{fmtDt(l.scheduled_at)}</span>
                <div className="lesson-info">
                  <div className="lesson-name">{l.student_name || 'Ученик не указан'}</div>
                  <div className="lesson-topic">{l.topic_name || 'Тема не указана'}</div>
                </div>
                <span className={`badge ${l.vcs_platform === 'zoom' ? 'badge-zoom' : 'badge-ya'}`}>
                  {l.vcs_platform === 'zoom' ? 'Zoom' : 'Телемост'}
                </span>
                {badge.cls && <span className={`badge ${badge.cls}`}>{badge.label}</span>}
                {(l.status === 'in_progress' || l.status === 'scheduled') && (
                  <button className="btn btn-sm" title="Следить за уроком"
                    onClick={() => window.__openMonitor?.(l.id)}
                    style={{ color: 'var(--color-accent)' }}>
                    <i className="ti ti-broadcast"></i>
                  </button>
                )}
                {l.vcs_link && (
                  <a href={l.vcs_link} className="btn btn-sm" target="_blank" rel="noreferrer">
                    <i className="ti ti-external-link"></i> Открыть
                  </a>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
