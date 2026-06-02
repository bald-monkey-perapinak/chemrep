import { useStore } from '../../store/useStore'
import { findNode, fileIcon, typeLabel, countChildren, formatSize } from '../../utils/helpers'

export default function KbDetail() {
  const kbTree = useStore((s) => s.kbTree)
  const selectedKbNode = useStore((s) => s.selectedKbNode)
  const deleteFile = useStore((s) => s.deleteFile)
  const addFiles = useStore((s) => s.addFiles)
  const addSubfolder = useStore((s) => s.addSubfolder)
  const showToast = useStore((s) => s.showToast)

  const node = selectedKbNode ? findNode(kbTree, selectedKbNode) : null

  function handleAddFile() {
    if (!selectedKbNode) { alert('Выберите тему в дереве'); return }
    if (!node || node.type !== 'topic') { alert('Выберите тему (не папку) для загрузки файла'); return }
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.onchange = () => {
      const files = Array.from(input.files).map((f) => ({
        name: f.name,
        size: formatSize(f.size),
        date: new Date().toLocaleDateString('ru'),
      }))
      addFiles(selectedKbNode, files)
    }
    input.click()
  }

  function handleAddSubfolder() {
    const name = prompt('Название подпапки:')
    if (!name || !name.trim()) return
    addSubfolder(selectedKbNode, name.trim())
    showToast(`Подпапка «${name.trim()}» создана`)
  }

  if (!node) {
    return (
      <div className="kb-detail">
        <div className="card">
          <div className="empty-state">
            <i className="ti ti-folder"></i>
            Выберите папку или тему слева
          </div>
        </div>
      </div>
    )
  }

  if (node.type === 'topic') {
    const files = node.files || []
    return (
      <div className="kb-detail">
        <div className="card">
          <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 4 }}>{node.name}</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
            Тема · {files.length} файлов
          </div>
          <div className="kb-files">
            {files.length === 0 ? (
              <div className="empty-state">
                <i className="ti ti-file-off"></i>
                Нет файлов
              </div>
            ) : (
              files.map((f) => (
                <div className="file-row" key={f.name}>
                  <i className={`ti ${fileIcon(f.name)} file-icon`}></i>
                  <div className="file-info">
                    <div className="file-name">{f.name}</div>
                    <div className="file-meta">{f.size} · {f.date}</div>
                  </div>
                  <button className="btn btn-sm"><i className="ti ti-download"></i></button>
                  <button className="btn btn-sm btn-danger" onClick={() => deleteFile(node.id, f.name)}>
                    <i className="ti ti-trash"></i>
                  </button>
                </div>
              ))
            )}
          </div>
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-sm btn-primary" onClick={handleAddFile}>
              <i className="ti ti-upload"></i> Загрузить файл
            </button>
          </div>
        </div>
      </div>
    )
  }

  const count = countChildren(node)
  return (
    <div className="kb-detail">
      <div className="card">
        <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 4 }}>{node.name}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
          {typeLabel(node.type)} · {count} элементов
        </div>
        <button className="btn btn-sm btn-primary" onClick={handleAddSubfolder}>
          <i className="ti ti-folder-plus"></i> Добавить подпапку
        </button>
      </div>
    </div>
  )
}
