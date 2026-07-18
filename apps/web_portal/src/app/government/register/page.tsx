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

export default function GovernmentRegisterPage() {
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
      setError('Passwords do not match.');
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
          : 'Registration failed. Please check your details and try again.'
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
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Government Portal Access</h1>
          <p className="text-sm text-gray-500 mt-2 max-w-xs">
            Restricted to pre-authorized health-authority email addresses. Registration will be
            rejected if your email hasn&apos;t been whitelisted by an existing administrator.
          </p>
        </div>

        {success ? (
          <div className="text-center space-y-4">
            <ShieldCheck className="mx-auto text-emerald-500" size={40} />
            <p className="text-gray-500">
              Account created. We&apos;ve sent a verification link to <strong>{email}</strong> — sign in once you&apos;ve clicked it.
            </p>
            <a href="/login" className="neu-button inline-block px-6 py-3 bg-purple-500 text-white font-bold rounded-xl">
              Go to Sign In
            </a>
          </div>
        ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="gov-fullname" className="block text-sm font-semibold mb-2">Full Name</label>
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
            <label htmlFor="gov-username" className="block text-sm font-semibold mb-2">Username</label>
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
            <label htmlFor="gov-email" className="block text-sm font-semibold mb-2">Authorized Email</label>
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
            <label htmlFor="gov-password" className="block text-sm font-semibold mb-2">Password</label>
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
            <p className="text-xs text-gray-500 mt-1">Minimum 8 characters.</p>
          </div>
          <div>
            <label htmlFor="gov-confirm-password" className="block text-sm font-semibold mb-2">Confirm Password</label>
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
            <ShieldCheck size={18} /> {submitting ? 'Verifying…' : 'Register Government Account'}
          </button>
        </form>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          Not a government official?{' '}
          <a href="/login" className="text-indigo-500 font-semibold hover:underline">Go to the main sign-in</a>
        </p>
      </motion.div>
    </div>
  );
}
