"use client";

// Previously apps/web_portal had NO login or registration page anywhere —
// AuthContext exposed a login() function that nothing in the UI ever
// called, so every "protected" page (booking, family profiles, doctor
// dashboard, consultation) was unreachable through a real session. This is
// the single biggest gap called out in the audit (Critical #13): the
// planning doc's very first step, "Secure login or registration," did not
// exist in this app at all.

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { LogIn, UserPlus } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';

type Mode = 'login' | 'register';
type Role = 'PATIENT' | 'DOCTOR';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<Role>('PATIENT');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const doLogin = async (loginUsername: string, loginPassword: string) => {
    // FastAPI's OAuth2PasswordRequestForm (used by POST /auth/login) expects
    // an application/x-www-form-urlencoded body with username/password
    // fields, not JSON — hence URLSearchParams + explicit content-type here
    // rather than the shared `api` client's default JSON header.
    const body = new URLSearchParams();
    body.set('username', loginUsername);
    body.set('password', loginPassword);

    const { data } = await api.post('/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    // /auth/login only returns { access_token, token_type, role } — fetch
    // the full profile (now including `id`, needed by booking/payment
    // ownership checks) before completing login.
    const meRes = await api.get('/auth/me', {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });

    login(data.access_token, meRes.data);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      if (mode === 'register') {
        await api.post('/auth/register', {
          username,
          password,
          email,
          full_name: fullName,
          role,
        });
        // Register endpoint doesn't return a token — log in immediately
        // with the credentials just created for a seamless flow.
        await doLogin(username, password);
      } else {
        await doLogin(username, password);
      }

      router.push('/');
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(
        typeof message === 'string'
          ? message
          : mode === 'login'
            ? 'Invalid username or password.'
            : 'Registration failed. Please check your details and try again.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40" />
        <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-teal-400 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel w-full max-w-md p-8"
      >
        <h1 className="text-3xl font-bold text-center mb-2 text-[var(--foreground)]">GramCare AI</h1>
        <p className="text-center text-gray-500 mb-8">
          {mode === 'login' ? 'Sign in to continue your care journey.' : 'Create your account.'}
        </p>

        <div className="flex mb-8 rounded-xl bg-white/40 dark:bg-black/40 p-1 border border-white/20">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'login' ? 'bg-indigo-500 text-white' : 'text-gray-500'}`}
          >
            <LogIn size={16} /> Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'register' ? 'bg-teal-500 text-white' : 'text-gray-500'}`}
          >
            <UserPlus size={16} /> Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-semibold mb-2">Username</label>
            <input
              required
              type="text"
              minLength={3}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
          </div>

          {mode === 'register' && (
            <>
              <div>
                <label className="block text-sm font-semibold mb-2">Full Name</label>
                <input
                  required
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Email</label>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">I am a...</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as Role)}
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                >
                  <option value="PATIENT">Patient</option>
                  <option value="DOCTOR">Doctor</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Pharmacists have a separate portal.
                </p>
              </div>
            </>
          )}

          <div>
            <label className="block text-sm font-semibold mb-2">Password</label>
            <input
              required
              type="password"
              minLength={mode === 'register' ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
            {mode === 'register' && (
              <p className="text-xs text-gray-500 mt-1">Minimum 8 characters.</p>
            )}
          </div>

          {error && (
            <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="neu-button w-full py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-50"
          >
            {submitting ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
