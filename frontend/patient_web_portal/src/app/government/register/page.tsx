"use client";

// Government Portal registration — POST /auth/register/government has
// existed on the backend since the doctor-verification workflow shipped,
// gated by AuthorizedGovernmentEmail (pre-provisioned, no self-serve
// application). Until now nothing in web_portal ever called it: the login
// page's role picker only offers Patient/Doctor/Hospital, so the only way
// to create a government account was a direct API request. Deliberately a
// separate, low-key route rather than a fourth option in the public role
// dropdown — a whitelist-gated, highest-privilege account shouldn't read as
// "pick this to register," and isolating it keeps a bug in the public
// registration flow from ever touching this one.

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Landmark, ShieldCheck } from 'lucide-react';
import api from '../../../lib/api';
import { useLocale } from '../../../contexts/LocaleContext';

export default function GovernmentRegisterPage() {
  const { t } = useLocale();
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError(t('passwords_dont_match'));
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/auth/register/government', {
        username,
        full_name: fullName,
        email,
        password,
      });
      // Government accounts must verify their email (same as every other
      // non-PATIENT role) before /auth/login will succeed — an immediate
      // login attempt here would just 403, so this stops at a clear
      // "check your inbox" state instead.
      setSuccess(true);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(
        typeof message === 'string'
          ? message
          : t('registration_failed_web')
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40" />
        <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel w-full max-w-md p-8"
      >
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-full bg-purple-500/15 flex items-center justify-center mb-3">
            <Landmark className="text-purple-500" size={26} />
          </div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">{t('gov_portal_access')}</h1>
          <p className="text-sm text-gray-500 mt-2 max-w-xs">
            {t('gov_portal_restricted_note')}
          </p>
        </div>

        {success ? (
          <div className="text-center space-y-4">
            <ShieldCheck className="mx-auto text-emerald-500" size={40} />
            <p className="text-gray-500">
              {t('gov_account_created_prefix')} <strong>{email}</strong> — {t('gov_account_created_suffix')}
            </p>
            <a href="/login" className="neu-button inline-block px-6 py-3 bg-purple-500 text-white font-bold rounded-xl">
              {t('go_to_sign_in')}
            </a>
          </div>
        ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="gov-fullname" className="block text-sm font-semibold mb-2">{t('full_name_label')}</label>
            <input
              id="gov-fullname"
              required
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-purple-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="gov-username" className="block text-sm font-semibold mb-2">{t('username')}</label>
            <input
              id="gov-username"
              required
              type="text"
              minLength={3}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-purple-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="gov-email" className="block text-sm font-semibold mb-2">{t('authorized_email')}</label>
            <input
              id="gov-email"
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-purple-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="gov-password" className="block text-sm font-semibold mb-2">{t('password')}</label>
            <input
              id="gov-password"
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-purple-400 focus:outline-none"
            />
            <p className="text-xs text-gray-500 mt-1">{t('min_8_chars')}</p>
          </div>
          <div>
            <label htmlFor="gov-confirm-password" className="block text-sm font-semibold mb-2">{t('confirm_password')}</label>
            <input
              id="gov-confirm-password"
              required
              type="password"
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-purple-400 focus:outline-none"
            />
          </div>

          {error && (
            <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="neu-button w-full py-3 bg-purple-500 text-white font-bold rounded-xl disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <ShieldCheck size={18} /> {submitting ? t('verifying_ellipsis') : t('register_gov_account')}
          </button>
        </form>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          {t('not_a_gov_official')}{' '}
          <a href="/login" className="text-indigo-500 font-semibold hover:underline">{t('go_to_main_signin')}</a>
        </p>
      </motion.div>
    </div>
  );
}
