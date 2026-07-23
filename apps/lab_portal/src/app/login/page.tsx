"use client";

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { LogIn, UserPlus, FlaskConical } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';

type Mode = 'login' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState('');
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
    setSubmitting(true);

    try {
      if (mode === 'register') {
        await api.post('/auth/register', {
          username,
          password,
          email,
          full_name: fullName,
          role: 'LAB',
        });
      }
      await doLogin(username, password);
      router.push('/dashboard');
    } catch (err) {
      if (err instanceof Error && err.message === 'ROLE_MISMATCH') {
        setError('This portal is for registered Laboratory accounts only.');
        localStorage.removeItem('lab_access_token');
      } else {
        const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(
          typeof message === 'string'
            ? message
            : mode === 'login'
              ? 'Invalid username or password.'
              : 'Registration failed. Please check your details and try again.'
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
        <div className="flex flex-col items-center mb-2">
          <FlaskConical size={40} className="text-[var(--primary)] mb-2" />
          <h1 className="text-3xl font-bold text-center text-[var(--foreground)]">GramCare Lab</h1>
        </div>
        <p className="text-center text-gray-500 mb-8">
          {mode === 'login' ? 'Sign in to your laboratory portal.' : 'Register your diagnostic center.'}
        </p>

        <div className="flex mb-8 rounded-xl bg-white/40 dark:bg-black/40 p-1 border border-white/20">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'login' ? 'bg-[var(--primary)] text-white' : 'text-gray-500'}`}
          >
            <LogIn size={16} /> Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'register' ? 'bg-purple-500 text-white' : 'text-gray-500'}`}
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
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
            />
          </div>

          {mode === 'register' && (
            <>
              <div>
                <label className="block text-sm font-semibold mb-2">Lab / Contact Name</label>
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
                <label className="block text-sm font-semibold mb-2">Email</label>
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

          <div>
            <label className="block text-sm font-semibold mb-2">Password</label>
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

          {error && (
            <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="neu-button w-full py-3 bg-[var(--primary)] text-white font-bold rounded-xl disabled:opacity-50"
          >
            {submitting ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Lab Account'}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
