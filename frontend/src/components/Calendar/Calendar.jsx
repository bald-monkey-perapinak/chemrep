import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { MONTHS, DAYS } from '../../utils/helpers'

export default function Calendar({ onOpenNewLesson }) {
  const lessons = useStore((s) => s.lessons)
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth())
  const [year, setYear] = useState(now.getFullYear())

  function changeMonth(d) {
    let m = month + d
    let y = year
    if (m > 11) { m = 0; y++ }
    if (m < 0) { m = 11; y-- }
    setMonth(m)
    setYear(y)
  }

  function goToday() {
    setMonth(now.getMonth())
    setYear(now.getFullYear())
  }

  const todayStr = now.toISOString().slice(0, 10)
  const first = new Date(year, month, 1)
  let startDow = first.getDay()
  if (startDow === 0) startDow = 7
  const dim = new Date(year, month + 1, 0).getDate()
  const dip = new Date(year, month, 0).getDate()

  const cells = []
  for (let i = startDow - 1; i > 0; i--) cells.push({ d: dip - i + 1, month: month - 1, other: true })
  for (let i = 1; i <= dim; i++) cells.push({ d: i, month, other: false })
  let rem = 42 - cells.length
  for (let i = 1; i <= rem; i++) cells.push({ d: i, month: month + 1, other: true })

  function calDayClick(ds) {
    onOpenNewLesson(ds)
  }

  return (
    <div>
      <div className="cal-header">
        <div className="cal-nav">
          <button className="btn btn-sm" onClick={() => changeMonth(-1)}><i className="ti ti-chevron-left"></i></button>
          <button className="btn btn-sm" onClick={() => changeMonth(1)}><i className="ti ti-chevron-right"></i></button>
        </div>
        <span className="cal-month">{MONTHS[month]} {year}</span>
        <button className="btn btn-sm" onClick={goToday}>Сегодня</button>
      </div>

      <div className="cal-grid">
        {DAYS.map((d) => (
          <div key={d} className="cal-day-header">{d}</div>
        ))}
        {cells.map((c, i) => {
          const ds = `${year}-${String(c.month + 1).padStart(2, '0')}-${String(c.d).padStart(2, '0')}`
          const isToday = ds === todayStr && !c.other
          const dayLessons = lessons.filter((l) => l.date === ds)
          return (
            <div
              key={i}
              className={`cal-day${c.other ? ' other-month' : ''}${isToday ? ' today' : ''}`}
              onClick={() => calDayClick(ds)}
            >
              <div className="day-num">{c.d}</div>
              {dayLessons.map((l) => (
                <div key={l.id} className={`day-event ${l.platform}`}>
                  {l.time} {l.student.split(' ')[0]}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
