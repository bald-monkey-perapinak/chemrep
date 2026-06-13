import './Skeleton.css'

export function SkeletonLine({ width = '100%', height = 16, style = {} }) {
  return <div className="skeleton-line" style={{ width, height, ...style }} />
}

export function SkeletonCard({ lines = 3, style = {} }) {
  return (
    <div className="skeleton-card" style={style}>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} width={i === lines - 1 ? '60%' : '100%'} />
      ))}
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
  return (
    <div className="skeleton-card" style={{ padding: 0 }}>
      <div className="skeleton-table-header">
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonLine key={i} width="80px" height={14} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="skeleton-table-row">
          {Array.from({ length: cols }).map((_, c) => (
            <SkeletonLine key={c} width={`${60 + Math.random() * 30}%`} height={14} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonLessons() {
  return <SkeletonTable rows={5} cols={6} />
}

export function SkeletonStudents() {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <SkeletonLine width="100px" height={14} />
        <SkeletonLine width="140px" height={32} />
      </div>
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonCard key={i} lines={2} style={{ marginBottom: 12 }} />
      ))}
    </div>
  )
}
