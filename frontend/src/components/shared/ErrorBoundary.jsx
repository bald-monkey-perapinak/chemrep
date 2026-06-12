import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <h2>Что-то пошло не так</h2>
          <p style={{ color: 'var(--color-text-muted)' }}>
            {this.state.error?.message || 'Неизвестная ошибка'}
          </p>
          <button className="btn" onClick={() => this.setState({ hasError: false })}>
            Попробовать снова
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
