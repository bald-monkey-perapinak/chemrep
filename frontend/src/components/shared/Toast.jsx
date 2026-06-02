import { useStore } from '../../store/useStore'

export default function Toast() {
  const toast = useStore((s) => s.toast)
  return (
    <div className={`toast-msg${toast ? ' show' : ''}`}>
      {toast}
    </div>
  )
}
