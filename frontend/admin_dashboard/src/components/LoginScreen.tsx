import { useState } from 'react';
import axios from 'axios';
import { useLocale } from '../contexts/LocaleContext';

interface LoginScreenProps {
  onLoginSuccess: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://gramcare-fastapi.onrender.com/api/v1';

type Mode = 'login' | 'register' | 'forgot';

/**
 * Pharmacist auth gate. Previously apps/react_dashboard had NO login screen
 * at all — every pharmacy API call was unauthenticated. Now that the backend
 * requires a PHARMACIST-role JWT for stock writes and the prescription
 * queue, this screen is the only way to obtain one.
 *
 * It also carries registration and password recovery, because this portal is
 * where the main web portal sends every pharmacist: that portal's role picker
 * deliberately offers only PATIENT/DOCTOR/HOSPITAL and links here instead.
 * With login as the only surface here, a new pharmacist had nowhere to sign
 * up and a locked-out one had nowhere to recover — a closed loop between the
 * two portals.
 *
 * FastAPI's OAuth2PasswordRequestForm (used by /auth/login) expects an
 * application/x-www-form-urlencoded body with `username`/`password` fields,
 * NOT JSON — hence the URLSearchParams body and explicit content-type below,
 * rather than using the shared `api` client's default JSON header. The
 * register and forgot-password endpoints are ordinary JSON.
 */
export default function LoginScreen({ onLoginSuccess }: LoginScreenProps) {
  const { t, code, setCode } = useLocale();
  const [mode, setMode] = useState<Mode>('login');

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');

  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const switchTo = (next: Mode) => {
    setMode(next);
    setError('');
    setInfo('');
  };

  const readError = (err: unknown, fallback: string) => {
    const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined;
    return typeof detail === 'string' ? detail : fallback;
  };

  const doLogin = async (identifier: string, secret: string) => {
    const body = new URLSearchParams();
    body.set('username', identifier);
    body.set('password', secret);

    const res = await axios.post(`${API_BASE_URL}/auth/login`, body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    const { access_token, refresh_token, role } = res.data;

    if (role !== 'PHARMACIST' && role !== 'ADMIN') {
      setError(t('not_a_pharmacist_account'));
      return false;
    }

    localStorage.setItem('pharmacy_access_token', access_token);
    localStorage.setItem('pharmacy_refresh_token', refresh_token);
    localStorage.setItem('pharmacy_user_role', role);
    onLoginSuccess();
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setSubmitting(true);

    try {
      if (mode === 'login') {
        await doLogin(username, password);
      } else if (mode === 'register') {
        await axios.post(`${API_BASE_URL}/auth/register`, {
          username,
          email,
          password,
          full_name: fullName,
          role: 'PHARMACIST',
          phone: phone || undefined,
        });
        // Sign straight in rather than stopping at "check your email":
        // PHARMACIST is not one of the roles the backend gates on email
        // verification, so an extra step here would be a dead end, not a
        // safeguard.
        const signedIn = await doLogin(username, password);
        if (!signedIn) {
          setInfo(t('account_created_pending_role'));
          switchTo('login');
        }
      } else {
        await axios.post(`${API_BASE_URL}/auth/forgot-password`, { email });
        setInfo(t('reset_link_sent'));
      }
    } catch (err) {
      setError(
        readError(
          err,
          mode === 'login'
            ? t('login_failed')
            : mode === 'register'
              ? t('registration_failed')
              : t('reset_link_failed'),
        ),
      );
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle = {
    width: '100%',
    padding: '0.6rem',
    marginBottom: '1rem',
    borderRadius: '8px',
    border: '1px solid #cbd5e0',
  } as const;

  const labelStyle = {
    display: 'block',
    marginBottom: '0.5rem',
    fontSize: '0.9rem',
  } as const;

  const linkStyle = {
    background: 'none',
    border: 'none',
    color: '#10b981',
    fontWeight: 600,
    cursor: 'pointer',
    padding: 0,
    fontSize: '0.85rem',
  } as const;

  const heading =
    mode === 'login' ? t('portal_title')
    : mode === 'register' ? t('create_pharmacist_account')
    : t('reset_your_password');

  const subheading =
    mode === 'login' ? t('sign_in_subtitle')
    : mode === 'register' ? t('register_subtitle')
    : t('forgot_subtitle');

  const submitLabel =
    submitting
      ? (mode === 'login' ? t('signing_in') : mode === 'register' ? t('creating_account') : t('sending'))
      : (mode === 'login' ? t('sign_in') : mode === 'register' ? t('create_account') : t('send_reset_link'));

  return (
    <div
      className="neo-glass-container"
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}
    >
      <form onSubmit={handleSubmit} className="glass-panel" style={{ width: '360px', padding: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
          <button
            type="button"
            onClick={() => setCode(code === 'en' ? 'ta' : 'en')}
            aria-label={t('language')}
            style={linkStyle}
          >
            {code === 'en' ? 'தமிழ்' : 'English'}
          </button>
        </div>
        <h1 style={{ marginTop: 0, fontSize: '1.75rem', color: '#10b981' }}>{heading}</h1>
        <p style={{ color: '#718096', marginBottom: '1.5rem' }}>{subheading}</p>

        {mode === 'register' && (
          <>
            <label style={labelStyle} htmlFor="pharm-fullname">{t('full_name')}</label>
            <input
              id="pharm-fullname"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              autoComplete="name"
              style={inputStyle}
            />
          </>
        )}

        {mode !== 'forgot' && (
          <>
            <label style={labelStyle} htmlFor="pharm-username">
              {mode === 'login' ? t('username_or_email') : t('username')}
            </label>
            <input
              id="pharm-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={mode === 'register' ? 3 : undefined}
              autoComplete="username"
              style={inputStyle}
            />
          </>
        )}

        {(mode === 'register' || mode === 'forgot') && (
          <>
            <label style={labelStyle} htmlFor="pharm-email">{t('email')}</label>
            <input
              id="pharm-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              style={inputStyle}
            />
          </>
        )}

        {mode === 'register' && (
          <>
            <label style={labelStyle} htmlFor="pharm-phone">{t('phone_optional')}</label>
            <input
              id="pharm-phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoComplete="tel"
              style={inputStyle}
            />
          </>
        )}

        {mode !== 'forgot' && (
          <>
            <label style={labelStyle} htmlFor="pharm-password">{t('password')}</label>
            <input
              id="pharm-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={mode === 'register' ? 8 : undefined}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              style={inputStyle}
            />
            {mode === 'register' && (
              <p style={{ color: '#718096', fontSize: '0.75rem', marginTop: '-0.75rem', marginBottom: '1rem' }}>
                {t('min_8_chars')}
              </p>
            )}
          </>
        )}

        {error && (
          <p role="alert" style={{ color: '#ef4444', fontSize: '0.9rem', marginBottom: '1rem' }}>
            {error}
          </p>
        )}
        {info && (
          <p role="status" style={{ color: '#10b981', fontSize: '0.9rem', marginBottom: '1rem' }}>
            {info}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="neu-button"
          style={{ width: '100%', padding: '0.75rem', fontWeight: 'bold' }}
        >
          {submitLabel}
        </button>

        <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
          {mode === 'login' ? (
            <>
              <button type="button" style={linkStyle} onClick={() => switchTo('register')}>
                {t('create_an_account')}
              </button>
              <button type="button" style={linkStyle} onClick={() => switchTo('forgot')}>
                {t('forgot_password')}
              </button>
            </>
          ) : (
            <button type="button" style={linkStyle} onClick={() => switchTo('login')}>
              {t('back_to_sign_in')}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
