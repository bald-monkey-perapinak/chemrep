import { useStore } from '../../store/useStore'
import { findNode, fileIcon, countChildren, formatSize } from '../../utils/helpers'
import ScriptEditor from './ScriptEditor'

export default function KbDetail() {
  const kbTree          = useStore(s => s.kbTree)
  const selectedKbNode  = useStore(s => s.selectedKbNode)
  const deleteFile      = useStore(s => s.deleteFile)
  const addFiles        = useStore(s => s.addFiles)
  const updateTopic     = useStore(s => s.updateTopic)
  const showToast       = useStore(s => s.showToast)

  const node = selectedKbNode ? findNode(kbTree, selectedKbNode) : null

  function handleAddFile() {
    if (!node || node.type !== 'topic') { alert('Выберите тему для загрузки файла'); return }
    const input = document.createElement('input')
    input.type = 'file'; input.multiple = true
    input.onchange = async () => {
      try {
        await addFiles(selectedKbNode, Array.from(input.files))
        showToast('Файлы загружены')
      } catch (e) {
        showToast('Ошибка: ' + e.message)
      }
    }
    input.click()
  }

  if (!node) return (
    <div className="kb-detail">
      <div className="card">
        <div className="empty-state"><i className="ti ti-folder"></i>Выберите папку или тему слева</div>
      </div>
    </div>
  )

  if (node.type === 'topic') {
    const files = node.files || []
    const script = node.lesson_script || []
    return (
      <div className="kb-detail">
        <div className="card">
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 4 }}>{node.name}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
            Тема · {files.length} файлов · {script.length} шагов сценария
          </div>
          <div className="kb-files">
            {files.length === 0 ? (
              <div className="empty-state"><i className="ti ti-file-off"></i>Нет файлов</div>
            ) : files.map(f => (
              <div className="file-row" key={f.id || f.name}>
                <i className={`ti ${fileIcon(f.name)} file-icon`}></i>
                <div className="file-info">
                  <div className="file-name">{f.name}</div>
                  <div className="file-meta">{f.size} · {f.date}</div>
                </div>
                <button className="btn btn-sm btn-danger"
                  onClick={async () => {
                    try {
                      await deleteFile(node.id, f.id || f.name)
                      showToast('Файл удалён')
                    } catch (e) { showToast('Ошибка: ' + e.message) }
                  }}>
                  <i className="ti ti-trash"></i>
                </button>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-sm btn-primary" onClick={handleAddFile}>
              <i className="ti ti-upload"></i> Загрузить файл
            </button>
          </div>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <ScriptEditor
            script={script}
            onChange={async (newScript) => {
              try {
                await updateTopic(node.id, { lesson_script: newScript })
                showToast('Сценарий сохранён')
              } catch (e) {
                showToast('Ошибка: ' + e.message)
              }
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="kb-detail">
      <div className="card">
        <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 4 }}>{node.name}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          Папка · {countChildren(node)} элементов
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--color-text-muted)' }}>
          Наведите курсор на элемент в дереве, чтобы добавить вложенную папку или тему.
        </div>
      </div>
    </div>
  )
}
