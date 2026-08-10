"use client";

// POST /auth/reset-password has existed on the backend since the
// password-reset workflow shipped, but nothing in the frontend ever linked
// here — /auth/forgot-password's emailed link pointed at this exact route
// with a ?token= query param, into a 404. Resetting also revokes every
// active session server-side (see modules/auth/router.py's reset_password),
// so this always ends by sending the user to sign in fresh rather than
// trying to auto-login them.

import React, { Suspense, useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter, useSearchParams } from 'next/navigation';
import { ShieldCheck } from 'lucide-react';
import api from '../../lib/api';
import { useLocale } from '../../contexts/LocaleContext';

function ResetPasswordForm() {
  const { t } = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError(t('passwords_dont_match'));
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: newPassword });
      setSuccess(true);
      setTimeout(() => router.push('/login'), 2500);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : t('invalid_reset_link'));
    } finally {
      setSubmitting(false);
    }
  };

  if (!token) {
    return (
      <div className="text-center space-y-6">
        <p role="alert" className="text-red-500 text-sm font-semibold">{t('invalid_reset_link')}</p>
        <a href="/forgot-password" className="text-sm font-semibold text-indigo-500 hover:underline">
          {t('reset_password')}
        </a>
      </div>
    );
  }

  if (success) {
    return (
      <div className="text-center space-y-6">
        <p role="status" className="text-emerald-500 text-sm font-semibold">{t('reset_password_success')}</p>
        <a href="/login" className="text-sm font-semibold text-indigo-500 hover:underline">
          {t('back_to_login')}
        </a>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="reset-new-password" className="block text-sm font-semibold mb-2">{t('new_password')}</label>
        <input
          id="reset-new-password"
          required
          type="password"
          minLength={8}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          autoComplete="new-password"
          className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
        />
        <p className="text-xs text-gray-500 mt-1">{t('min_8_chars')}</p>
      </div>

      <div>
        <label htmlFor="reset-confirm-password" className="block text-sm font-semibold mb-2">{t('confirm_password')}</label>
        <input
          id="reset-confirm-password"
          required
          type="password"
          minLength={8}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          autoComplete="new-password"
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
        {submitting ? t('please_wait') : t('reset_password')}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  const { t } = useLocale();
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
          <ShieldCheck size={22} className="text-indigo-500" /> {t('reset_password')}
        </h1>
        <Suspense fallback={<p className="text-center text-gray-400 text-sm">{t('please_wait')}</p>}>
          <ResetPasswordForm />
        </Suspense>
      </motion.div>
    </div>
  );
}
