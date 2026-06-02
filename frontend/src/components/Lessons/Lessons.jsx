import { useStore } from '../../store/useStore'
import { fmtDate } from '../../utils/helpers'

export default function Lessons() {
  const lessons = useStore((s) => s.lessons)
  const deleteLesson = useStore((s) => s.deleteLesson)

  const sorted = [...lessons].sort((a, b) =>
    a.date + a.time < b.date + b.time ? 1 : -1
  )

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <table className="lessons-table">
        <thead>
          <tr>
            <th>Дата и время</th>
            <th>Ученик</th>
            <th>Тема</th>
            <th>Платформа</th>
            <th>Ссылка</th>
            <th>Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((l) => (
            <tr key={l.id}>
              <td>{fmtDate(l.date)}, {l.time}</td>
              <td style={{ fontWeight: 500 }}>{l.student}</td>
              <td>{l.topic}</td>
              <td>
                <span className={`badge ${l.platform === 'zoom' ? 'badge-zoom' : 'badge-ya'}`}>
                  {l.platform === 'zoom' ? 'Zoom' : 'Яндекс Телемост'}
                </span>
              </td>
              <td>
                <a href={l.link} className="link-btn" target="_blank" rel="noreferrer">
                  <i className="ti ti-external-link"></i> Открыть
                </a>
              </td>
              <td>
                <span className={`badge ${l.status === 'done' ? 'badge-active' : 'badge-upcoming'}`}>
                  {l.status === 'done' ? 'Завершено' : 'Предстоит'}
                </span>
              </td>
              <td>
                <button className="btn btn-sm btn-danger" onClick={() => deleteLesson(l.id)}>
                  <i className="ti ti-trash"></i>
                </button>
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--color-text-muted)' }}>
                Нет занятий
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
