"use client";

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { LogIn, UserPlus, FlaskConical } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useLocale } from '../../contexts/LocaleContext';

type Mode = 'login' | 'register' | 'forgot';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { t, code, setCode } = useLocale();

  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const doLogin = async (loginUsername: string, loginPassword: string) => {
    // FastAPI's OAuth2PasswordRequestForm expects a form-encoded body, not JSON.
    const body = new URLSearchParams();
    body.set('username', loginUsername);
    body.set('password', loginPassword);

    const { data } = await api.post('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    const meRes = await api.get('/auth/me', {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });

    if (meRes.data.role !== 'LAB') {
      throw new Error('ROLE_MISMATCH');
    }

    login(data.access_token, data.refresh_token, meRes.data);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setSubmitting(true);

    try {
      if (mode === 'forgot') {
        await api.post('/auth/forgot-password', { email });
        setInfo(t('reset_link_sent'));
        return;
      }
      if (mode === 'register') {
        await api.post('/auth/register', {
          username,
          password,
          email,
          full_name: fullName,
          role: 'LAB',
        });
      }
      await doLogin(username.trim(), password);
      router.push('/dashboard');
    } catch (err) {
      if (err instanceof Error && err.message === 'ROLE_MISMATCH') {
        setError(t('lab_accounts_only'));
        localStorage.removeItem('lab_access_token');
      } else {
        const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(
          typeof message === 'string'
            ? message
            : mode === 'login'
              ? t('invalid_credentials')
              : mode === 'forgot'
                ? t('reset_link_failed')
                : t('registration_failed')
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel w-full max-w-md p-8"
      >
        <div className="flex justify-end mb-1">
          <button
            type="button"
            onClick={() => setCode(code === 'en' ? 'ta' : 'en')}
            aria-label={t('language')}
            className="text-sm font-semibold text-[var(--primary)] hover:underline"
          >
            {code === 'en' ? 'தமிழ்' : 'English'}
          </button>
        </div>
        <div className="flex flex-col items-center mb-2">
          <FlaskConical size={40} className="text-[var(--primary)] mb-2" />
          <h1 className="text-3xl font-bold text-center text-[var(--foreground)]">{t('lab_portal')}</h1>
        </div>
        <p className="text-center text-gray-500 mb-8">
          {mode === 'login'
            ? t('login_blurb')
            : mode === 'register'
              ? t('register_blurb')
              : t('forgot_blurb')}
        </p>

        <div className="flex mb-8 rounded-xl bg-white/40 dark:bg-black/40 p-1 border border-white/20">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(''); setInfo(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'login' ? 'bg-[var(--primary)] text-white' : 'text-gray-500'}`}
          >
            <LogIn size={16} /> {t('sign_in')}
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(''); setInfo(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'register' ? 'bg-purple-500 text-white' : 'text-gray-500'}`}
          >
            <UserPlus size={16} /> {t('register')}
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode !== 'forgot' && (
          <div>
            <label className="block text-sm font-semibold mb-2">
              {mode === 'login' ? t('username_or_email') : t('username')}
            </label>
            <input
              required
              type="text"
              minLength={3}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
            />
          </div>
          )}

          {mode === 'forgot' && (
            <div>
              <label className="block text-sm font-semibold mb-2">{t('email')}</label>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              />
            </div>
          )}

          {mode === 'register' && (
            <>
              <div>
                <label className="block text-sm font-semibold mb-2">{t('lab_contact_name')}</label>
                <input
                  required
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">{t('email')}</label>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
                />
              </div>
            </>
          )}

          {mode !== 'forgot' && (
          <div>
            <label className="block text-sm font-semibold mb-2">{t('password')}</label>
            <input
              required
              type="password"
              minLength={mode === 'register' ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
            />
          </div>
          )}

          {error && (
            <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>
          )}
          {info && (
            <p role="status" className="text-emerald-500 text-sm font-semibold text-center">{info}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="neu-button w-full py-3 bg-[var(--primary)] text-white font-bold rounded-xl disabled:opacity-50"
          >
            {submitting
              ? t('please_wait')
              : mode === 'login'
                ? t('sign_in')
                : mode === 'register'
                  ? t('create_lab_account')
                  : t('send_reset_link')}
          </button>

          <p className="text-center text-sm">
            {mode === 'forgot' ? (
              <button
                type="button"
                onClick={() => { setMode('login'); setError(''); setInfo(''); }}
                className="text-[var(--primary)] font-semibold hover:underline"
              >
                {t('back_to_sign_in')}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => { setMode('forgot'); setError(''); setInfo(''); }}
                className="text-gray-500 font-semibold hover:underline"
              >
                {t('forgot_password')}
              </button>
            )}
          </p>
        </form>
      </motion.div>
    </div>
  );
}
