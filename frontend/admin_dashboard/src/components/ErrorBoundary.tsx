import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { LOCALE_STORAGE_KEY } from '../contexts/LocaleContext';

// A class component cannot use the useLocale hook, and this boundary has to
// keep working even when the failure is inside the provider tree it would
// otherwise read from — so it reads the same stored locale directly.
const COPY = {
  en: {
    title: 'Something went wrong',
    body: 'This dashboard hit an unexpected error. Your inventory data is safe — reload to try again.',
    reload: 'Reload',
  },
  ta: {
    title: 'ஏதோ தவறு நடந்துவிட்டது',
    body: 'இந்த டாஷ்போர்டில் எதிர்பாராத பிழை ஏற்பட்டது. உங்கள் இருப்புத் தரவு பாதுகாப்பாக உள்ளது — மீண்டும் ஏற்றி முயற்சிக்கவும்.',
    reload: 'மீண்டும் ஏற்று',
  },
} as const;

function copy() {
  try {
    return localStorage.getItem(LOCALE_STORAGE_KEY) === 'ta' ? COPY.ta : COPY.en;
  } catch {
    return COPY.en;
  }
}

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
      const c = copy();
      return (
        <div className="neo-glass-container" style={{ maxWidth: 480, margin: '4rem auto', textAlign: 'center' }}>
          <AlertTriangle size={48} color="#ef4444" style={{ margin: '0 auto 1rem' }} />
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: 8 }}>{c.title}</h1>
          <p style={{ color: '#718096', fontSize: '0.9rem', marginBottom: 24 }}>
            {c.body}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="neu-button"
            style={{ background: '#10b981', color: 'white', display: 'inline-flex', alignItems: 'center', gap: 8 }}
          >
            <RotateCcw size={16} /> {c.reload}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
