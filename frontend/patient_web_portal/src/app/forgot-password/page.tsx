"use client";

// POST /auth/forgot-password has existed on the backend since the
// password-reset workflow shipped, but no frontend anywhere ever called
// it — the login page had no "forgot password" link at all, so a locked-out
// user had no self-service recovery path. Deliberately mirrors the
// email-enumeration-safe response the backend already returns (always the
// same generic success message, whether or not the email is registered).

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { KeyRound } from 'lucide-react';
import api from '../../lib/api';
import { useLocale } from '../../contexts/LocaleContext';

export default function ForgotPasswordPage() {
  const { t } = useLocale();
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await api.post('/auth/forgot-password', { email });
      setSent(true);
    } catch {
      // Network-level failure only — the backend itself never returns a
      // "not found" error here (email-enumeration-safe by design).
      setError(t('network_error'));
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
        <h1 className="text-2xl font-bold text-center mb-2 text-[var(--foreground)] flex items-center justify-center gap-2">
          <KeyRound size={22} className="text-indigo-500" /> {t('reset_password')}
        </h1>
        <p className="text-center text-gray-500 mb-8 text-sm">{t('reset_password_tagline')}</p>

        {sent ? (
          <div className="text-center space-y-6">
            <p role="status" className="text-emerald-500 text-sm font-semibold">{t('reset_link_sent')}</p>
            <a href="/login" className="text-sm font-semibold text-indigo-500 hover:underline">
              {t('back_to_login')}
            </a>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="forgot-email" className="block text-sm font-semibold mb-2">{t('email')}</label>
              <input
                id="forgot-email"
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
              />
            </div>

            {error && (
              <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="neu-button w-full py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-50"
            >
              {submitting ? t('please_wait') : t('send_reset_link')}
            </button>

            <p className="text-center">
              <a href="/login" className="text-xs font-semibold text-gray-500 hover:underline">
                {t('back_to_login')}
              </a>
            </p>
          </form>
        )}
      </motion.div>
    </div>
  );
}
