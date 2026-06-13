import { useStore } from '../../store/useStore'
import { fmtDt } from '../../utils/helpers'
import { SkeletonLessons } from '../shared/Skeleton'

const STATUS = {
  scheduled:   { cls: 'badge-upcoming', label: 'Запланировано' },
  in_progress: { cls: 'badge-active',   label: 'Идёт сейчас' },
  completed:   { cls: 'badge-active',   label: 'Завершено' },
  cancelled:   { cls: 'badge-ya',       label: 'Отменено' },
  missed:      { cls: 'badge-ya',       label: 'Пропущено' },
}

export default function Lessons() {
  const lessons       = useStore(s => s.lessons)
  const deleteLesson  = useStore(s => s.deleteLesson)
  const showToast     = useStore(s => s.showToast)
  const lessonsLoading = useStore(s => s.lessonsLoading)

  if (lessonsLoading) {
    return <SkeletonLessons />
  }

  const sorted = [...lessons].sort((a, b) => a.scheduled_at > b.scheduled_at ? -1 : 1)

  async function remove(id) {
    if (!confirm('Удалить занятие?')) return
    await deleteLesson(id)
    showToast('Занятие удалено')
  }

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table className="lessons-table">
        <thead>
          <tr>
            <th>Дата и время</th><th>Ученик</th><th>Тема</th>
            <th>Платформа</th><th>Статус</th><th>Сессия</th><th></th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(l => {
            const badge = STATUS[l.status] || { cls: '', label: l.status }
            const sess  = l.session
            return (
              <tr key={l.id}>
                <td>{fmtDt(l.scheduled_at)}</td>
                <td style={{ fontWeight: 500 }}>{l.student_name || '—'}</td>
                <td>{l.topic_name || '—'}</td>
                <td>
                  <span className={`badge ${l.vcs_platform === 'zoom' ? 'badge-zoom' : 'badge-ya'}`}>
                    {l.vcs_platform === 'zoom' ? 'Zoom' : 'Телемост'}
                  </span>
                </td>
                <td><span className={`badge ${badge.cls}`}>{badge.label}</span></td>
                <td>
                  {sess ? (
                    <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                      {sess.status === 'active' ? `Шаг ${sess.current_step}/${sess.total_steps}` : sess.status}
                    </span>
                  ) : '—'}
                </td>
                <td style={{ display: 'flex', gap: 6 }}>
                  {(l.status === 'in_progress' || l.status === 'scheduled') && (
                    <button className="btn btn-sm" title="Следить за уроком"
                      onClick={() => window.__openMonitor?.(l.id)}
                      style={{ color: 'var(--color-accent)' }}>
                      Live
                    </button>
                  )}
                  {l.vcs_link && (
                    <a href={l.vcs_link} className="btn btn-sm" target="_blank" rel="noreferrer">
                      Ссылка
                    </a>
                  )}
                  <button className="btn btn-sm btn-danger" onClick={() => remove(l.id)}>
                    Удалить
                  </button>
                </td>
              </tr>
            )
          })}
          {sorted.length === 0 && (
            <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-muted)' }}>
              Нет занятий
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
