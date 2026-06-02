import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { findNode } from '../../utils/helpers'
import { CreateNodeModal, RenameNodeModal, DeleteNodeModal } from './FolderModals'

function TreeNode({ node, depth = 0, siblingNames }) {
  const selectedKbNode = useStore((s) => s.selectedKbNode)
  const setSelectedKbNode = useStore((s) => s.setSelectedKbNode)
  const renameNode = useStore((s) => s.renameNode)
  const deleteNode = useStore((s) => s.deleteNode)
  const addChildNode = useStore((s) => s.addChildNode)
  const showToast = useStore((s) => s.showToast)

  const [hovered, setHovered] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [createChildOpen, setCreateChildOpen] = useState(false)
  const [createTopicOpen, setCreateTopicOpen] = useState(false)

  const isSelected = selectedKbNode === node.id
  const isTopic = node.type === 'topic'
  const icon = isTopic ? 'ti-file-text' : 'ti-folder'
  const childNames = (node.children || []).map((c) => c.name)

  return (
    <div>
      <div
        className={`tree-item${isSelected ? ' selected' : ''}`}
        style={{ paddingLeft: depth * 16 + 8 }}
        onClick={() => setSelectedKbNode(node.id)}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        <i className={`ti ${icon}`} style={{ flexShrink: 0 }}></i>
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {node.name}
        </span>

        {hovered && (
          <span style={{ display: 'flex', gap: 2, marginLeft: 4 }} onClick={(e) => e.stopPropagation()}>
            {!isTopic && (
              <>
                <button className="icon-btn" title="Добавить папку" onClick={() => setCreateChildOpen(true)}>
                  <i className="ti ti-folder-plus" style={{ fontSize: 12 }}></i>
                </button>
                <button className="icon-btn" title="Добавить тему" onClick={() => setCreateTopicOpen(true)}>
                  <i className="ti ti-file-plus" style={{ fontSize: 12 }}></i>
                </button>
              </>
            )}
            <button className="icon-btn" title="Переименовать" onClick={() => setRenameOpen(true)}>
              <i className="ti ti-pencil" style={{ fontSize: 12 }}></i>
            </button>
            <button className="icon-btn del" title="Удалить" onClick={() => setDeleteOpen(true)}>
              <i className="ti ti-trash" style={{ fontSize: 12 }}></i>
            </button>
          </span>
        )}
      </div>

      {node.children && node.children.map((child) => (
        <TreeNode
          key={child.id}
          node={child}
          depth={depth + 1}
          siblingNames={node.children.map((c) => c.name)}
        />
      ))}

      {createChildOpen && (
        <CreateNodeModal
          title="Новая папка"
          label="Название папки"
          placeholder="Название"
          existingNames={childNames}
          onClose={() => setCreateChildOpen(false)}
          onConfirm={(name) => {
            addChildNode(node.id, name, 'folder')
            setCreateChildOpen(false)
            showToast(`Папка «${name}» создана`)
          }}
        />
      )}

      {createTopicOpen && (
        <CreateNodeModal
          title="Новая тема"
          label="Название темы"
          placeholder="Например: Алканы"
          existingNames={childNames}
          onClose={() => setCreateTopicOpen(false)}
          onConfirm={(name) => {
            addChildNode(node.id, name, 'topic')
            setCreateTopicOpen(false)
            showToast(`Тема «${name}» создана`)
          }}
        />
      )}

      {renameOpen && (
        <RenameNodeModal
          currentName={node.name}
          existingNames={siblingNames}
          onClose={() => setRenameOpen(false)}
          onConfirm={(name) => {
            renameNode(node.id, name)
            setRenameOpen(false)
            showToast(`Переименовано в «${name}»`)
          }}
        />
      )}

      {deleteOpen && (
        <DeleteNodeModal
          name={node.name}
          onClose={() => setDeleteOpen(false)}
          onConfirm={() => {
            deleteNode(node.id)
            setDeleteOpen(false)
            showToast(`«${node.name}» удалено`)
          }}
        />
      )}
    </div>
  )
}

export default function KbTree() {
  const kbTree = useStore((s) => s.kbTree)
  const rootNames = kbTree.map((n) => n.name)

  return (
    <div className="kb-tree">
      {kbTree.map((node) => (
        <TreeNode key={node.id} node={node} depth={0} siblingNames={rootNames} />
      ))}
      {kbTree.length === 0 && (
        <div style={{ padding: 16, fontSize: 13, color: 'var(--color-text-muted)', textAlign: 'center' }}>
          Нет папок
        </div>
      )}
    </div>
  )
}
