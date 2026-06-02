export default function Modal({ children, onClose, width }) {
  return (
    <div className="modal-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal" style={width ? { width } : {}}>
        {children}
      </div>
    </div>
  )
}
