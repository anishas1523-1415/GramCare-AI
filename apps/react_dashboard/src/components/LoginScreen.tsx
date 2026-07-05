import { useState } from 'react';
import axios from 'axios';

interface LoginScreenProps {
  onLoginSuccess: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://gramcare-fastapi.onrender.com/api/v1';

/**
 * Pharmacist login gate. Previously apps/react_dashboard had NO login screen
 * at all — every pharmacy API call was unauthenticated. Now that the backend
 * requires a PHARMACIST-role JWT for stock writes and the prescription
 * queue, this screen is the only way to obtain one.
 *
 * FastAPI's OAuth2PasswordRequestForm (used by /auth/login) expects an
 * application/x-www-form-urlencoded body with `username`/`password` fields,
 * NOT JSON — hence the URLSearchParams body and explicit content-type below,
 * rather than using the shared `api` client's default JSON header.
 */
export default function LoginScreen({ onLoginSuccess }: LoginScreenProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      const body = new URLSearchParams();
      body.set('username', username);
      body.set('password', password);

      const res = await axios.post(`${API_BASE_URL}/auth/login`, body, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const { access_token, role } = res.data;

      if (role !== 'PHARMACIST' && role !== 'ADMIN') {
        setError('This account is not a pharmacist account.');
        setSubmitting(false);
        return;
      }

      localStorage.setItem('pharmacy_access_token', access_token);
      localStorage.setItem('pharmacy_user_role', role);
      onLoginSuccess();
    } catch (err) {
      const message = axios.isAxiosError(err)
        ? err.response?.data?.detail || 'Login failed'
        : 'Login failed';
      setError(String(message));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="neo-glass-container"
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}
    >
      <form onSubmit={handleSubmit} className="glass-panel" style={{ width: '360px', padding: '2rem' }}>
        <h1 style={{ marginTop: 0, fontSize: '1.75rem', color: '#10b981' }}>GramCare Pharmacy Portal</h1>
        <p style={{ color: '#718096', marginBottom: '1.5rem' }}>Sign in with your pharmacist account.</p>

        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Username</label>
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          autoComplete="username"
          style={{ width: '100%', padding: '0.6rem', marginBottom: '1rem', borderRadius: '8px', border: '1px solid #cbd5e0' }}
        />

        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem' }}>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
          style={{ width: '100%', padding: '0.6rem', marginBottom: '1rem', borderRadius: '8px', border: '1px solid #cbd5e0' }}
        />

        {error && (
          <p role="alert" style={{ color: '#ef4444', fontSize: '0.9rem', marginBottom: '1rem' }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="neu-button"
          style={{ width: '100%', padding: '0.75rem', fontWeight: 'bold' }}
        >
          {submitting ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}
