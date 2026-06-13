import { useState, useRef } from 'react'
import { api } from '../../utils/api'

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

const SAMPLE_SCRIPT = [
  {
    "step": 1,
    "text": "Сегодня мы изучим тему...",
    "question": "",
    "board_commands": [],
    "listen": false,
    "speak_only": false,
    "difficulty": "easy",
    "key_concepts": []
  },
  {
    "step": 2,
    "text": "Объяснение нового материала...",
    "question": "Можешь повторить определение?",
    "board_commands": [{"type": "draw_text", "text": "Ключевое понятие"}],
    "listen": true,
    "speak_only": false,
    "difficulty": "normal",
    "key_concepts": ["ключевое понятие"]
  }
]

const SAMPLE_TXT = `1. Введение в тему
Объяснение базовых понятий. Сегодня мы разберём основные определения.

2. Основной материал
Подробное описание темы с примерами и иллюстрациями.

3. Практика
Предложите ученику решить задачу или ответить на вопрос.

4. Закрепление
Повторите ключевые моменты и подведите итоги урока.`

function parseTxtToScript(text) {
  const lines = text.split('\n').filter(l => l.trim())
  const steps = []
  let currentStep = null

  for (const line of lines) {
    const trimmed = line.trim()

    // Проверяем является ли строка заголовком шага
    // Форматы: "1. ", "1) ", "Шаг 1: ", "# ", "## "
    const stepMatch = trimmed.match(/^(?:\d+[\.\)]\s*|Шаг\s+\d+[:\s]*|#{1,2}\s+)(.+)/i)

    if (stepMatch) {
      if (currentStep) steps.push(currentStep)
      currentStep = {
        step: steps.length + 1,
        text: stepMatch[1].trim(),
        question: '',
        board_commands: [],
        listen: false,
        speak_only: false,
        difficulty: 'normal',
        key_concepts: [],
      }
    } else if (currentStep) {
      // Добавляем текст к текущему шагу
      if (trimmed.startsWith('?') || trimmed.endsWith('?')) {
        currentStep.question = trimmed.replace(/^\?/, '').trim()
        currentStep.listen = true
      } else {
        currentStep.text = currentStep.text ? currentStep.text + ' ' + trimmed : trimmed
      }
    } else {
      // Текст до первого заголовка — первый шаг
      currentStep = {
        step: 1,
        text: trimmed,
        question: '',
        board_commands: [],
        listen: false,
        speak_only: false,
        difficulty: 'normal',
        key_concepts: [],
      }
    }
  }

  if (currentStep) steps.push(currentStep)

  // Если шагов нет, разбиваем по пустым строкам
  if (steps.length === 0) {
    const paragraphs = text.split(/\n\s*\n/).filter(p => p.trim())
    return paragraphs.map((p, i) => ({
      step: i + 1,
      text: p.trim().replace(/\n/g, ' '),
      question: '',
      board_commands: [],
      listen: false,
      speak_only: false,
      difficulty: 'normal',
      key_concepts: [],
    }))
  }

  return steps.map((s, i) => ({ ...s, step: i + 1 }))
}

function parseJsonToScript(data) {
  if (!Array.isArray(data)) return null
  if (data.length === 0) return null

  for (let i = 0; i < data.length; i++) {
    const step = data[i]
    if (!step.text && step.text !== '') return null
    if (step.board_commands && !Array.isArray(step.board_commands)) return null
  }

  return data.map((s, i) => ({
    step: i + 1,
    text: s.text || '',
    question: s.question || '',
    board_commands: (s.board_commands || []).map(cmd => {
      const normalized = { type: cmd.type || 'draw_text' }
      if (cmd.smiles) normalized.smiles = cmd.smiles
      if (cmd.equation) normalized.equation = cmd.equation
      if (cmd.label) normalized.label = cmd.label
      if (cmd.text) normalized.text = cmd.text
      if (cmd.x) normalized.x = cmd.x
      if (cmd.y) normalized.y = cmd.y
      return normalized
    }),
    listen: s.listen !== false,
    speak_only: s.speak_only === true,
    difficulty: ['easy', 'normal', 'hard'].includes(s.difficulty) ? s.difficulty : 'normal',
    key_concepts: Array.isArray(s.key_concepts) ? s.key_concepts : [],
  }))
}

function parseFileToScript(text, filename) {
  const ext = filename.split('.').pop().toLowerCase()

  if (ext === 'json') {
    const data = JSON.parse(text)
    const script = parseJsonToScript(data)
    if (!script) throw new Error('JSON не содержит массив шагов с полем "text"')
    return script
  }

  if (ext === 'txt' || ext === 'md' || ext === 'markdown' || ext === 'text') {
    const script = parseTxtToScript(text)
    if (script.length === 0) throw new Error('Не удалось извлечь шаги из файла')
    return script
  }

  // PDF и DOCX обрабатываются через бэкенд
  return null
}

export default function ScriptEditor({ script = [], onChange }) {
  const [expanded, setExpanded] = useState(null)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState('')
  const fileInputRef = useRef(null)

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

  function handleFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return

    setImportError('')
    setImporting(true)

    const ext = file.name.split('.').pop().toLowerCase()
    const isBinary = ['pdf', 'docx'].includes(ext)

    if (isBinary) {
      // PDF/DOCX — отправляем на бэкенд для извлечения текста
      const formData = new FormData()
      formData.append('file', file)

      fetch('/api/extract/text', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: formData,
      })
        .then(res => {
          if (!res.ok) return res.json().then(d => { throw new Error(d.detail || 'Ошибка сервера') })
          return res.json()
        })
        .then(data => {
          const script = parseTxtToScript(data.text)
          if (script.length === 0) {
            setImportError('Не удалось извлечь шаги из файла')
            setImporting(false)
            return
          }
          if (script.length > 50) {
            setImportError('Слишком много шагов (максимум 50)')
            setImporting(false)
            return
          }
          if (script.length > 0) {
            if (!confirm(`Заменить текущий сценарий (${script.length} шагов) на загруженный?`)) {
              setImporting(false)
              return
            }
          }
          onChange(script)
          setImporting(false)
        })
        .catch(err => {
          setImportError(err.message || 'Ошибка чтения файла')
          setImporting(false)
        })
    } else {
      // JSON/TXT/MD — читаем на клиенте
      const reader = new FileReader()
      reader.onload = (ev) => {
        try {
          const text = ev.target.result
          const script = parseFileToScript(text, file.name)

          if (!script) {
            setImportError('Не удалось обработать файл')
            setImporting(false)
            return
          }

          if (script.length === 0) {
            setImportError('Не удалось извлечь шаги из файла')
            setImporting(false)
            return
          }

          if (script.length > 50) {
            setImportError('Слишком много шагов (максимум 50)')
            setImporting(false)
            return
          }

          if (script.length > 0) {
            if (!confirm(`Заменить текущий сценарий (${script.length} шагов) на загруженный?`)) {
              setImporting(false)
              return
            }
          }

          onChange(script)
          setImporting(false)
        } catch (err) {
          setImportError(err.message || 'Ошибка чтения файла')
          setImporting(false)
        }
      }
      reader.readAsText(file)
    }
    e.target.value = ''
  }

  function downloadTemplate(format) {
    let content, type, filename

    if (format === 'json') {
      content = JSON.stringify(SAMPLE_SCRIPT, null, 2)
      type = 'application/json'
      filename = 'lesson_script.json'
    } else {
      content = SAMPLE_TXT
      type = 'text/plain'
      filename = 'lesson_script.txt'
    }

    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="script-editor">
      <div className="script-header">
        <span style={{ fontWeight: 500 }}>Сценарий урока</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            {script.length} шагов
          </span>
          <button className="btn btn-sm" onClick={() => downloadTemplate('json')} title="Скачать шаблон JSON">
            JSON
          </button>
          <button className="btn btn-sm" onClick={() => downloadTemplate('txt')} title="Скачать шаблон TXT">
            TXT
          </button>
          <button className="btn btn-sm btn-primary" onClick={() => fileInputRef.current?.click()} disabled={importing}>
            {importing ? 'Загрузка...' : 'Импорт файла'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.txt,.md,.markdown,.text,.pdf,.docx"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />
        </div>
      </div>

      {importError && (
        <div style={{
          padding: '8px 12px', marginBottom: 8, fontSize: 12,
          background: '#FCEBEB', color: '#A32D2D', borderRadius: 6,
        }}>
          {importError}
        </div>
      )}

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
                  ^
                </button>
                <button onClick={() => moveStep(i, 1)} disabled={i === script.length - 1} title="Вниз">
                  v
                </button>
                <button onClick={() => removeStep(i)} title="Удалить" className="btn-danger">
                  X
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

                {!step.speak_only && (
                  <div className="board-commands">
                    <div className="board-commands-header">
                      <label>Команды доски</label>
                      <button className="btn btn-sm" onClick={() => addBoardCommand(i)}>
                        + Добавить
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
                          X
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
        + Добавить шаг
      </button>
    </div>
  )
}
