import { useState } from 'react'

const EMPTY_STEP = {
  step: 0,
  text: '',
  question: '',
  board_commands: [],
  listen: true,
  speak_only: false,
  difficulty: 'normal',
  key_concepts: [],
}

const BOARD_COMMAND_TYPES = [
  { value: 'show_formula', label: 'Формула (SMILES)', fields: ['smiles', 'label'] },
  { value: 'show_equation', label: 'Уравнение реакции', fields: ['equation', 'label'] },
  { value: 'draw_text', label: 'Текст на доске', fields: ['text'] },
  { value: 'clear_step', label: 'Очистить доску', fields: [] },
]

export default function ScriptEditor({ script = [], onChange }) {
  const [expanded, setExpanded] = useState(null)

  function updateStep(i, patch) {
    const next = script.map((s, idx) => idx === i ? { ...s, ...patch } : s)
    onChange(next)
  }

  function addStep() {
    const next = [...script, { ...EMPTY_STEP, step: script.length + 1 }]
    onChange(next)
    setExpanded(next.length - 1)
  }

  function removeStep(i) {
    const next = script.filter((_, idx) => idx !== i).map((s, idx) => ({ ...s, step: idx + 1 }))
    onChange(next)
    if (expanded === i) setExpanded(null)
  }

  function moveStep(i, dir) {
    const j = i + dir
    if (j < 0 || j >= script.length) return
    const next = [...script]
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next.map((s, idx) => ({ ...s, step: idx + 1 })))
    setExpanded(j)
  }

  function addBoardCommand(i) {
    const step = script[i]
    const cmds = [...(step.board_commands || []), { type: 'draw_text', text: '' }]
    updateStep(i, { board_commands: cmds })
  }

  function updateBoardCommand(stepIdx, cmdIdx, patch) {
    const cmds = script[stepIdx].board_commands.map((c, ci) => ci === cmdIdx ? { ...c, ...patch } : c)
    updateStep(stepIdx, { board_commands: cmds })
  }

  function removeBoardCommand(stepIdx, cmdIdx) {
    const cmds = script[stepIdx].board_commands.filter((_, ci) => ci !== cmdIdx)
    updateStep(stepIdx, { board_commands: cmds })
  }

  return (
    <div className="script-editor">
      <div className="script-header">
        <span style={{ fontWeight: 500 }}>Сценарий урока</span>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          {script.length} шагов
        </span>
      </div>

      <div className="script-steps">
        {script.map((step, i) => (
          <div key={i} className={`script-step ${expanded === i ? 'expanded' : ''}`}>
            <div className="script-step-header" onClick={() => setExpanded(expanded === i ? null : i)}>
              <span className="step-num">{step.step}</span>
              <span className="step-preview">
                {step.text ? step.text.slice(0, 60) + (step.text.length > 60 ? '...' : '') : '(пусто)'}
              </span>
              <span className={`step-difficulty badge-${step.difficulty}`}>
                {step.difficulty}
              </span>
              <div className="step-actions" onClick={e => e.stopPropagation()}>
                <button onClick={() => moveStep(i, -1)} disabled={i === 0} title="Вверх">
                  <i className="ti ti-chevron-up"></i>
                </button>
                <button onClick={() => moveStep(i, 1)} disabled={i === script.length - 1} title="Вниз">
                  <i className="ti ti-chevron-down"></i>
                </button>
                <button onClick={() => removeStep(i)} title="Удалить" className="btn-danger">
                  <i className="ti ti-trash"></i>
                </button>
              </div>
            </div>

            {expanded === i && (
              <div className="script-step-body">
                <div className="field">
                  <label>Текст шага (озвучивается)</label>
                  <textarea
                    value={step.text}
                    onChange={e => updateStep(i, { text: e.target.value })}
                    placeholder="Алканы — это предельные углеводороды..."
                    rows={3}
                  />
                </div>

                <div className="field">
                  <label>Проверочный вопрос</label>
                  <input
                    value={step.question || ''}
                    onChange={e => updateStep(i, { question: e.target.value })}
                    placeholder="Можешь назвать формулу метана?"
                  />
                </div>

                <div className="field-row">
                  <div className="field" style={{ flex: 1 }}>
                    <label>Сложность</label>
                    <select
                      value={step.difficulty}
                      onChange={e => updateStep(i, { difficulty: e.target.value })}
                    >
                      <option value="easy">Лёгкий</option>
                      <option value="normal">Обычный</option>
                      <option value="hard">Сложный</option>
                    </select>
                  </div>
                  <div className="field" style={{ flex: 1 }}>
                    <label>Ключевые концепции</label>
                    <input
                      value={(step.key_concepts || []).join(', ')}
                      onChange={e => updateStep(i, {
                        key_concepts: e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                      })}
                      placeholder="алканы, углеводороды"
                    />
                  </div>
                </div>

                <div className="field-row">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={step.listen !== false}
                      onChange={e => updateStep(i, { listen: e.target.checked })}
                    />
                    Слушать ответ ученика
                  </label>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={step.speak_only === true}
                      onChange={e => updateStep(i, { speak_only: e.target.checked })}
                    />
                    Только голос (без доски)
                  </label>
                </div>

                {/* Board commands */}
                {!step.speak_only && (
                  <div className="board-commands">
                    <div className="board-commands-header">
                      <label>Команды доски</label>
                      <button className="btn btn-sm" onClick={() => addBoardCommand(i)}>
                        <i className="ti ti-plus"></i> Добавить
                      </button>
                    </div>
                    {(step.board_commands || []).map((cmd, ci) => (
                      <div key={ci} className="board-cmd">
                        <select
                          value={cmd.type}
                          onChange={e => updateBoardCommand(i, ci, {
                            type: e.target.value,
                            ...Object.fromEntries(
                              BOARD_COMMAND_TYPES.find(t => t.value === e.target.value)
                                ?.fields.map(f => [f, cmd[f] || '']) || []
                            )
                          })}
                        >
                          {BOARD_COMMAND_TYPES.map(t => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                          ))}
                        </select>
                        {cmd.type === 'show_formula' && (
                          <>
                            <input
                              value={cmd.smiles || ''}
                              onChange={e => updateBoardCommand(i, ci, { smiles: e.target.value })}
                              placeholder="SMILES: CC(=O)O"
                            />
                            <input
                              value={cmd.label || ''}
                              onChange={e => updateBoardCommand(i, ci, { label: e.target.value })}
                              placeholder="Название"
                            />
                          </>
                        )}
                        {cmd.type === 'show_equation' && (
                          <>
                            <input
                              value={cmd.equation || ''}
                              onChange={e => updateBoardCommand(i, ci, { equation: e.target.value })}
                              placeholder="CH4 + 2O2 -> CO2 + 2H2O"
                            />
                            <input
                              value={cmd.label || ''}
                              onChange={e => updateBoardCommand(i, ci, { label: e.target.value })}
                              placeholder="Название"
                            />
                          </>
                        )}
                        {cmd.type === 'draw_text' && (
                          <input
                            value={cmd.text || ''}
                            onChange={e => updateBoardCommand(i, ci, { text: e.target.value })}
                            placeholder="Текст на доске"
                            style={{ flex: 1 }}
                          />
                        )}
                        <button
                          className="btn btn-sm btn-danger"
                          onClick={() => removeBoardCommand(i, ci)}
                        >
                          <i className="ti ti-x"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <button className="btn btn-sm btn-primary" onClick={addStep} style={{ marginTop: 8 }}>
        <i className="ti ti-plus"></i> Добавить шаг
      </button>
    </div>
  )
}
