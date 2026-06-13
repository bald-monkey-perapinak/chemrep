import { useState } from 'react'
import { useStore } from '../../store/useStore'
import KbTree from './KbTree'
import KbDetail from './KbDetail'
import { CreateNodeModal, RenameNodeModal, DeleteNodeModal } from './FolderModals'

export default function KnowledgeBase() {
  const showToast = useStore((s) => s.showToast)
  const addRootFolder = useStore((s) => s.addRootFolder)
  const kbTree = useStore((s) => s.kbTree)
  const selectedKbNode = useStore((s) => s.selectedKbNode)
  const addFiles = useStore((s) => s.addFiles)

  const [createRootOpen, setCreateRootOpen] = useState(false)

  const allRootNames = kbTree.map((f) => f.name)

  function handleAddFile() {
    if (!selectedKbNode) { alert('Выберите тему в дереве'); return }
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.onchange = () => {
      addFiles(selectedKbNode, Array.from(input.files))
    }
    input.click()
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ fontSize: 15, fontWeight: 500 }}>
          База знаний
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-sm btn-primary" onClick={() => setCreateRootOpen(true)}>
            + Новая папка
          </button>
          <button className="btn btn-sm" onClick={handleAddFile}>
            Загрузить файл
          </button>
        </div>
      </div>

      {kbTree.length === 0 ? (
        <div className="custom-empty" style={{ marginBottom: 24 }}>
          Нет папок. Нажмите «Новая папка», чтобы создать структуру.
        </div>
      ) : (
        <div className="kb-layout">
          <KbTree />
          <KbDetail />
        </div>
      )}

      {createRootOpen && (
        <CreateNodeModal
          title="Новая папка"
          label="Название папки"
          placeholder="Например: 8 класс"
          existingNames={allRootNames}
          onClose={() => setCreateRootOpen(false)}
          onConfirm={async (name) => {
            await addRootFolder(name)
            setCreateRootOpen(false)
            showToast(`Папка «${name}» создана`)
          }}
        />
      )}
    </div>
  )
}
