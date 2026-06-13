import { useState, useEffect, useRef } from 'react'
import { useSSE } from '../../hooks/useSSE'

const KIND_LABELS = {
  session_started:  { icon: 'ti-player-play',    text: 'Урок начат',              color: '#3B6D11' },
  bot_joined:       { icon: 'ti-robot',           text: 'Бот вошёл в конференцию', color: '#185FA5' },
  step_started:     { icon: 'ti-list-numbers',    text: 'Шаг сценария',            color: '#534AB7' },
  board_action:     { icon: 'ti-layout-board',    text: 'Действие на доске',       color: '#854F0B' },
  question_asked:   { icon: 'ti-help-circle',     text: 'Вопрос ученику',          color: '#185FA5' },
  student_speech:   { icon: 'ti-message-circle',  text: 'Ученик ответил',          color: '#3B6D11' },
  student_question: { icon: 'ti-question-mark',   text: 'Вопрос от ученика',       color: '#534AB7' },
  bot_reply:        { icon: 'ti-robot',           text: 'Ответ бота',              color: '#185FA5' },
  homework_sent:    { icon: 'ti-mail-check',      text: 'ДЗ отправлено',           color: '#3B6D11' },
  session_ended:    { icon: 'ti-circle-check',    text: 'Урок завершён',           color: '#3B6D11' },
  session_failed:   { icon: 'ti-alert-circle',    text: 'Ошибка',                 color: '#A32D2D' },
  connected:        { icon: 'ti-wifi',            text: 'Подключено',              color: '#6b6b66' },
}

function fmtTime(isoTs) {
  const d = new Date(isoTs)
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
}

function StatusDot({ status }) {
  const colors = {
    connecting:   '#854F0B',
    connected:    '#3B6D11',
    disconnected: '#6b6b66',
    error:        '#A32D2D',
  }
  const labels = {
    connecting:   'Подключение…',
    connected:    'Live',
    disconnected: 'Отключено',
    error:        'Ошибка соединения',
  }
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: colors[status] }}>
      <span style={{
        width: 7, height: 7, borderRadius: '50%',
        background: colors[status],
        boxShadow: status === 'connected' ? `0 0 0 2px ${colors[status]}33` : 'none',
        animation: status === 'connected' ? 'pulse 2s infinite' : 'none',
      }} />
      {labels[status]}
    </span>
  )
}

/**
 * LessonMonitor — панель мониторинга урока в реальном времени.
 *
 * Props:
 *   lessonId  — UUID урока для подписки
 *   onClose   — коллбэк закрытия панели
 */
export default function LessonMonitor({ lessonId, onClose }) {
  const { events, status, lastEvent, clear } = useSSE(lessonId)
  const bottomRef = useRef(null)

  // Прогресс из последнего step_started
  const stepEvent = [...events].reverse().find(e => e.kind === 'step_started')
  const step  = stepEvent?.data?.step  || 0
  const total = stepEvent?.data?.total || 0

  // Последняя реплика диалога
  const lastDialog = [...events].reverse().find(
    e => ['student_speech', 'student_question', 'bot_reply', 'question_asked'].includes(e.kind)
  )

  // Авто-скролл к новым событиям
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  const isActive = ['session_started', 'bot_joined', 'step_started',
                    'board_action', 'question_asked', 'student_speech',
                    'student_question', 'bot_reply'].includes(lastEvent?.kind)
  const isEnded  = ['session_ended', 'session_failed'].includes(lastEvent?.kind)

  return (
    <>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>

      <div style={{
        position: 'fixed', bottom: 24, right: 24, width: 380,
        background: 'var(--color-surface)',
        border: '0.5px solid var(--color-border)',
        borderRadius: 12,
        boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
        display: 'flex', flexDirection: 'column',
        maxHeight: 520, zIndex: 200,
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '12px 16px',
          borderBottom: '0.5px solid var(--color-border)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 500 }}>Мониторинг урока</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <StatusDot status={status} />
            <button className="icon-btn" onClick={onClose} title="Закрыть">
              X
            </button>
          </div>
        </div>

        {/* Progress bar */}
        {total > 0 && (
          <div style={{ padding: '10px 16px 0', flexShrink: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between',
              fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 5 }}>
              <span>Прогресс по сценарию</span>
              <span>{step} / {total}</span>
            </div>
            <div style={{ height: 4, background: 'var(--color-bg)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${total ? (step / total) * 100 : 0}%`,
                background: 'var(--color-accent)',
                borderRadius: 2,
                transition: 'width 0.4s ease',
              }} />
            </div>
          </div>
        )}

        {/* Last dialog bubble */}
        {lastDialog && (
          <div style={{ padding: '10px 16px 0', flexShrink: 0 }}>
            <div style={{
              background: 'var(--color-bg)',
              borderRadius: 8, padding: '8px 12px',
              fontSize: 12, lineHeight: 1.5,
              borderLeft: `3px solid ${
                lastDialog.kind === 'student_speech' || lastDialog.kind === 'student_question'
                  ? '#534AB7' : 'var(--color-accent)'}`,
            }}>
              <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginBottom: 3 }}>
                {lastDialog.kind.startsWith('student') ? '👤 Ученик' : '🤖 Бот'}
              </div>
              {lastDialog.data?.text || lastDialog.data?.question || '—'}
            </div>
          </div>
        )}

        {/* Event log */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '10px 16px' }}>
          {events.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '20px 0',
              fontSize: 13, color: 'var(--color-text-muted)' }}>
              Ожидаем события…
            </div>
          ) : (
            events.map((e, i) => {
              const meta = KIND_LABELS[e.kind] || { icon: 'ti-dot', text: e.kind, color: '#6b6b66' }
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8,
                  marginBottom: 8, opacity: isEnded && i < events.length - 1 ? 0.6 : 1,
                }}>
                  <i className={`ti ${meta.icon}`}
                    style={{ fontSize: 14, color: meta.color, flexShrink: 0, marginTop: 1 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 500, color: meta.color }}>
                      {meta.text}
                      {e.kind === 'step_started' && e.data?.step &&
                        <span style={{ fontWeight: 400, color: 'var(--color-text-muted)' }}>
                          {' '}— шаг {e.data.step}/{e.data.total}
                        </span>}
                    </div>
                    {e.data?.text && (
                      <div style={{ fontSize: 11, color: 'var(--color-text-muted)',
                        marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap' }}>
                        {e.data.text}
                      </div>
                    )}
                    {e.data?.question && (
                      <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 1 }}>
                        {e.data.question}
                      </div>
                    )}
                    {e.data?.action && (
                      <div style={{ fontSize: 11, color: 'var(--color-text-muted)',
                        fontFamily: 'monospace', marginTop: 1 }}>
                        {e.data.action}
                      </div>
                    )}
                  </div>
                  <span style={{ fontSize: 10, color: 'var(--color-text-muted)',
                    flexShrink: 0, marginTop: 2 }}>
                    {fmtTime(e.ts)}
                  </span>
                </div>
              )
            })
          )}
          <div ref={bottomRef} />
        </div>

        {/* Footer */}
        {isEnded && (
          <div style={{
            padding: '10px 16px',
            borderTop: '0.5px solid var(--color-border)',
            fontSize: 12, color: 'var(--color-text-muted)',
            textAlign: 'center', flexShrink: 0,
          }}>
            {lastEvent?.kind === 'session_ended'
              ? '✓ Урок завершён успешно'
              : '⚠ Урок завершился с ошибкой'}
          </div>
        )}
      </div>
    </>
  )
}
