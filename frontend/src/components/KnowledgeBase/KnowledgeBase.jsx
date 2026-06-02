import { useState } from 'react'
import { useStore, SYSTEM_FOLDERS } from '../../store/useStore'
import { plural } from '../../utils/helpers'
import KbTree from './KbTree'
import KbDetail from './KbDetail'
import { CreateFolderModal, RenameFolderModal, DeleteFolderModal } from './FolderModals'
import { formatSize } from '../../utils/helpers'

export default function KnowledgeBase() {
  const customFolders = useStore((s) => s.customFolders)
  const addCustomFolder = useStore((s) => s.addCustomFolder)
  const renameCustomFolder = useStore((s) => s.renameCustomFolder)
  const deleteCustomFolder = useStore((s) => s.deleteCustomFolder)
  const showToast = useStore((s) => s.showToast)
  const selectedKbNode = useStore((s) => s.selectedKbNode)
  const addFiles = useStore((s) => s.addFiles)

  const [createOpen, setCreateOpen] = useState(false)
  const [renameTarget, setRenameTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const allNames = [...SYSTEM_FOLDERS, ...customFolders].map((f) => f.name)

  function handleAddFile() {
    if (!selectedKbNode) { alert('Выберите тему в дереве'); return }
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ fontSize: 15, fontWeight: 500 }}>
          <i className="ti ti-books" style={{ fontSize: 18, verticalAlign: -3, marginRight: 8 }}></i>
          Материалы
        </span>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-sm btn-primary" onClick={() => setCreateOpen(true)}>
            <i className="ti ti-folder-plus"></i> Новая папка
          </button>
          <button className="btn btn-sm" onClick={handleAddFile}>
            <i className="ti ti-upload"></i> Загрузить файл
          </button>
        </div>
      </div>

      {/* System folders */}
      <div className="kb-section-divider">
        <div className="kb-divider-line"></div>
        <span className="kb-section-label">Системные папки</span>
        <div className="kb-divider-line"></div>
      </div>
      <div className="folder-grid">
        {SYSTEM_FOLDERS.map((f) => (
          <div className="folder-card" key={f.id} style={{ cursor: 'default' }}>
            <i className={`ti ${f.icon} folder-card-icon`}></i>
            <div className="folder-card-name">{f.name}</div>
            <div className="folder-card-meta">{f.count} материал{plural(f.count)}</div>
            <span className="system-badge">Системная</span>
          </div>
        ))}
      </div>

      {/* Custom folders */}
      <div className="kb-section-divider" style={{ marginTop: 20 }}>
        <div className="kb-divider-line"></div>
        <span className="kb-section-label">Мои папки</span>
        <div className="kb-divider-line"></div>
      </div>

      {customFolders.length === 0 ? (
        <div className="custom-empty">
          <i className="ti ti-folder-off" style={{ fontSize: 28, display: 'block', marginBottom: 8, opacity: 0.35 }}></i>
          Нет пользовательских папок.<br />Нажмите «Новая папка», чтобы создать.
        </div>
      ) : (
        <div className="folder-grid">
          {customFolders.map((f) => (
            <div className="folder-card" key={f.id}>
              <div className="folder-card-actions">
                <button
                  className="icon-btn"
                  title="Переименовать"
                  onClick={(e) => { e.stopPropagation(); setRenameTarget(f) }}
                >
                  <i className="ti ti-pencil" style={{ fontSize: 13 }}></i>
                </button>
                <button
                  className="icon-btn del"
                  title="Удалить"
                  onClick={(e) => { e.stopPropagation(); setDeleteTarget(f) }}
                >
                  <i className="ti ti-trash" style={{ fontSize: 13 }}></i>
                </button>
              </div>
              <i className={`ti ${f.icon} folder-card-icon`}></i>
              <div className="folder-card-name">{f.name}</div>
              <div className="folder-card-meta">{f.count} материал{plural(f.count)}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tree + Detail */}
      <div style={{ marginTop: 24 }}>
        <div className="kb-layout">
          <KbTree />
          <KbDetail />
        </div>
      </div>

      {/* Modals */}
      {createOpen && (
        <CreateFolderModal
          existingNames={allNames}
          onClose={() => setCreateOpen(false)}
          onConfirm={(name) => {
            addCustomFolder(name)
            setCreateOpen(false)
            showToast(`Папка «${name}» создана`)
          }}
        />
      )}
      {renameTarget && (
        <RenameFolderModal
          folder={renameTarget}
          existingNames={allNames}
          onClose={() => setRenameTarget(null)}
          onConfirm={(name) => {
            const old = renameTarget.name
            renameCustomFolder(renameTarget.id, name)
            setRenameTarget(null)
            showToast(`«${old}» переименована в «${name}»`)
          }}
        />
      )}
      {deleteTarget && (
        <DeleteFolderModal
          folder={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onConfirm={() => {
            const name = deleteTarget.name
            deleteCustomFolder(deleteTarget.id)
            setDeleteTarget(null)
            showToast(`Папка «${name}» удалена`)
          }}
        />
      )}
    </div>
  )
}
