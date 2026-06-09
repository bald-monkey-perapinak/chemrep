export default function Settings() {
  return (
    <div style={{ maxWidth: 560 }}>
      <div className="card">
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>
          <i className="ti ti-settings" style={{ marginRight: 8 }}></i>Настройки
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>
          Настройки профиля и клонирование голоса доступны после подключения бэкенда.
        </div>
      </div>
    </div>
  )
}
