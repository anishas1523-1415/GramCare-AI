import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

// React error boundaries can only be class components — no hook equivalent
// exists. Without this, an unhandled render error anywhere in the pharmacy
// dashboard previously produced a blank white screen with no recovery path.
interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('GramCare Pharmacy Dashboard — unhandled error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="neo-glass-container" style={{ maxWidth: 480, margin: '4rem auto', textAlign: 'center' }}>
          <AlertTriangle size={48} color="#ef4444" style={{ margin: '0 auto 1rem' }} />
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: 8 }}>Something went wrong</h1>
          <p style={{ color: '#718096', fontSize: '0.9rem', marginBottom: 24 }}>
            This dashboard hit an unexpected error. Your inventory data is safe — reload to try again.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="neu-button"
            style={{ background: '#10b981', color: 'white', display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <RotateCcw size={16} /> Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
