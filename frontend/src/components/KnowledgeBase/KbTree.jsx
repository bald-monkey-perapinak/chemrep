import { useStore } from '../../store/useStore'
import { findNode } from '../../utils/helpers'

function TreeNodes({ nodes, depth = 0 }) {
  const selectedKbNode = useStore((s) => s.selectedKbNode)
  const setSelectedKbNode = useStore((s) => s.setSelectedKbNode)

  return nodes.map((n) => {
    const icon = n.type === 'class' ? 'ti-school' : n.type === 'section' ? 'ti-folder' : n.type === 'topic' ? 'ti-file-text' : 'ti-file'
    return (
      <div key={n.id}>
        <div
          className={`tree-item${selectedKbNode === n.id ? ' selected' : ''}`}
          style={depth > 0 ? { paddingLeft: depth * 16 + 8 } : {}}
          onClick={() => setSelectedKbNode(n.id)}
        >
          <i className={`ti ${icon}`}></i>
          {n.name}
        </div>
        {n.children && <TreeNodes nodes={n.children} depth={depth + 1} />}
      </div>
    )
  })
}

export default function KbTree() {
  const kbTree = useStore((s) => s.kbTree)
  return (
    <div className="kb-tree">
      <TreeNodes nodes={kbTree} />
    </div>
  )
}
