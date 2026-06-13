export default function NotFound() {
  return (
    <div style={{ padding: 40, textAlign: 'center' }}>
      <h2>404</h2>
      <p style={{ color: 'var(--color-text-muted)' }}>Страница не найдена</p>
      <a href="/" className="btn">На главную</a>
    </div>
  )
}
