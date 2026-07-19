"use client";

// Previously apps/web_portal had NO login or registration page anywhere —
// AuthContext exposed a login() function that nothing in the UI ever
// called, so every "protected" page (booking, family profiles, doctor
// dashboard, consultation) was unreachable through a real session. This is
// the single biggest gap called out in the audit (Critical #13): the
// planning doc's very first step, "Secure login or registration," did not
// exist in this app at all.
//
// Registration now also has to satisfy two newer server-side gates:
// - DOCTOR/HOSPITAL must verify a phone number (OTP via MSG91) before
//   POST /auth/register will even accept the submission.
// - Every non-PATIENT role must click an emailed verification link before
//   POST /auth/login will succeed — so registering as one of those roles
//   can no longer auto-login the way PATIENT still does; it lands back on
//   the sign-in tab with a "check your email" message instead.

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { LogIn, UserPlus, Phone, ShieldCheck } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useLocale } from '../../contexts/LocaleContext';

type Mode = 'login' | 'register';
type Role = 'PATIENT' | 'DOCTOR' | 'HOSPITAL';

const PHONE_VERIFIED_ROLES: Role[] = ['DOCTOR', 'HOSPITAL'];

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { t } = useLocale();

  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<Role>('PATIENT');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [phoneVerified, setPhoneVerified] = useState(false);
  const [sendingOtp, setSendingOtp] = useState(false);
  const [verifyingOtp, setVerifyingOtp] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showResend, setShowResend] = useState(false);
  const [resendEmail, setResendEmail] = useState('');
  const [resending, setResending] = useState(false);

  const needsPhoneVerification = mode === 'register' && PHONE_VERIFIED_ROLES.includes(role);

  const resetPhoneState = () => {
    setPhone('');
    setOtp('');
    setOtpSent(false);
    setPhoneVerified(false);
  };

  const sendOtp = async () => {
    setError('');
    setSendingOtp(true);
    try {
      await api.post('/auth/phone/send-otp', { phone });
      setOtpSent(true);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Could not send OTP. Check the number and try again.');
    } finally {
      setSendingOtp(false);
    }
  };

  const verifyOtp = async () => {
    setError('');
    setVerifyingOtp(true);
    try {
      await api.post('/auth/phone/verify-otp', { phone, otp });
      setPhoneVerified(true);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Incorrect OTP.');
    } finally {
      setVerifyingOtp(false);
    }
  };

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
    return meRes.data.role as string;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setSubmitting(true);

    try {
      if (mode === 'register') {
        await api.post('/auth/register', {
          username,
          password,
          email,
          full_name: fullName,
          role,
          phone: needsPhoneVerification ? phone : (role === 'PATIENT' && phone ? phone : undefined),
        });

        if (role !== 'PATIENT') {
          // DOCTOR/HOSPITAL (and every other non-PATIENT role) must click
          // an emailed verification link before login will succeed — an
          // immediate login attempt here would just 403.
          setMode('login');
          setPassword('');
          setInfo("Account created. We've sent a verification link to your email — sign in once you've clicked it.");
          setSubmitting(false);
          return;
        }
        // PATIENT stays low-friction: register endpoint doesn't return a
        // token, so log in immediately with the credentials just created.
      }
      const loggedInRole = await doLogin(username, password);

      // Land each role on its own home (hospital desks go straight to the
      // Emergency Desk — seconds matter there).
      router.push(
        loggedInRole === 'HOSPITAL' ? '/hospital'
        : loggedInRole === 'DOCTOR' ? '/doctor/dashboard'
        : loggedInRole === 'ADMIN' ? '/authority'
        : '/'
      );
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(
        typeof message === 'string'
          ? message
          : mode === 'login'
            ? 'Invalid username or password.'
            : 'Registration failed. Please check your details and try again.'
      );
      setShowResend(typeof message === 'string' && message.toLowerCase().includes('verify your email'));
    } finally {
      setSubmitting(false);
    }
  };

  const resendVerification = async () => {
    const target = resendEmail || email;
    if (!target) return;
    setResending(true);
    setError('');
    try {
      await api.post('/auth/resend-verification', { email: target });
      setInfo('If that email is registered and unverified, a new verification link has been sent.');
      setShowResend(false);
    } finally {
      setResending(false);
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
        <h1 className="text-3xl font-bold text-center mb-2 text-[var(--foreground)]">{t('app_title')}</h1>
        <p className="text-center text-gray-500 mb-8">
          {mode === 'login' ? t('sign_in_tagline') : t('create_account_tagline')}
        </p>

        <div className="flex mb-8 rounded-xl bg-white/40 dark:bg-black/40 p-1 border border-white/20">
          <button
            type="button"
            onClick={() => { setMode('login'); setError(''); setInfo(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'login' ? 'bg-indigo-500 text-white' : 'text-gray-500'}`}
          >
            <LogIn size={16} /> {t('sign_in')}
          </button>
          <button
            type="button"
            onClick={() => { setMode('register'); setError(''); setInfo(''); }}
            className={`flex-1 py-2 rounded-lg font-semibold flex items-center justify-center gap-2 transition-colors ${mode === 'register' ? 'bg-teal-500 text-white' : 'text-gray-500'}`}
          >
            <UserPlus size={16} /> {t('register')}
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-username" className="block text-sm font-semibold mb-2">{t('username')}</label>
            <input
              id="login-username"
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
                <label htmlFor="login-fullname" className="block text-sm font-semibold mb-2">{t('full_name')}</label>
                <input
                  id="login-fullname"
                  required
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                />
              </div>
              <div>
                <label htmlFor="login-email" className="block text-sm font-semibold mb-2">{t('email')}</label>
                <input
                  id="login-email"
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">{t('i_am_a')}</label>
                <select
                  value={role}
                  onChange={(e) => { setRole(e.target.value as Role); resetPhoneState(); }}
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                >
                  <option value="PATIENT">{t('patient')}</option>
                  <option value="DOCTOR">{t('doctor')}</option>
                  <option value="HOSPITAL">{t('hospital')}</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  {t('pharmacists_labs_note')}
                </p>
              </div>

              {role === 'PATIENT' && (
                <div>
                  <label htmlFor="login-patient-phone" className="block text-sm font-semibold mb-2 flex items-center gap-1.5">
                    <Phone size={14} /> {t('phone_number_optional')}
                  </label>
                  <input
                    id="login-patient-phone"
                    type="tel"
                    placeholder="+91XXXXXXXXXX"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    {t('phone_reminder_note')}
                  </p>
                </div>
              )}

              {needsPhoneVerification && (
                <div className="p-3 rounded-xl bg-white/30 dark:bg-black/10 border border-white/20 space-y-2">
                  <label className="block text-sm font-semibold flex items-center gap-1.5">
                    <Phone size={14} /> Phone Number
                  </label>
                  {phoneVerified ? (
                    <p className="text-sm text-emerald-500 font-semibold flex items-center gap-1.5">
                      <ShieldCheck size={15} /> {phone} verified
                    </p>
                  ) : (
                    <>
                      <div className="flex gap-2">
                        <input
                          required
                          type="tel"
                          placeholder="+91XXXXXXXXXX"
                          value={phone}
                          onChange={(e) => { setPhone(e.target.value); setOtpSent(false); }}
                          disabled={otpSent}
                          className="flex-1 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-indigo-400 focus:outline-none disabled:opacity-60"
                        />
                        <button
                          type="button"
                          onClick={sendOtp}
                          disabled={!phone || sendingOtp || otpSent}
                          className="neu-button px-3 py-2 text-xs font-bold rounded-lg whitespace-nowrap disabled:opacity-50"
                        >
                          {sendingOtp ? 'Sending…' : otpSent ? 'Sent' : 'Send OTP'}
                        </button>
                      </div>
                      {otpSent && (
                        <div className="flex gap-2">
                          <input
                            required
                            type="text"
                            inputMode="numeric"
                            placeholder="6-digit OTP"
                            value={otp}
                            onChange={(e) => setOtp(e.target.value)}
                            className="flex-1 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-indigo-400 focus:outline-none"
                          />
                          <button
                            type="button"
                            onClick={verifyOtp}
                            disabled={!otp || verifyingOtp}
                            className="neu-button px-3 py-2 text-xs font-bold rounded-lg whitespace-nowrap disabled:opacity-50"
                          >
                            {verifyingOtp ? 'Verifying…' : 'Verify'}
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}

          <div>
            <label htmlFor="login-password" className="block text-sm font-semibold mb-2">{t('password')}</label>
            <input
              id="login-password"
              required
              type="password"
              minLength={mode === 'register' ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
            {mode === 'register' && (
              <p className="text-xs text-gray-500 mt-1">{t('min_8_chars')}</p>
            )}
          </div>

          {error && (
            <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>
          )}
          {showResend && (
            <div className="p-3 rounded-xl bg-white/30 dark:bg-black/10 border border-white/20 space-y-2">
              <input
                type="email"
                placeholder="Your email"
                value={resendEmail}
                onChange={(e) => setResendEmail(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-indigo-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={resendVerification}
                disabled={resending || !(resendEmail || email)}
                className="w-full text-sm font-bold text-indigo-500 disabled:opacity-50"
              >
                {resending ? 'Sending…' : 'Resend verification email'}
              </button>
            </div>
          )}
          {info && (
            <p role="status" className="text-emerald-500 text-sm font-semibold text-center">{info}</p>
          )}

          <button
            type="submit"
            disabled={submitting || (needsPhoneVerification && !phoneVerified)}
            className="neu-button w-full py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-50"
          >
            {submitting ? t('please_wait') : mode === 'login' ? t('sign_in') : t('create_account')}
          </button>
        </form>

        <p className="text-center text-xs text-gray-400 mt-6">
          {t('government_official_prompt')}{' '}
          <a href="/government/register" className="text-purple-500 font-semibold hover:underline">{t('portal_access')}</a>
        </p>
      </motion.div>
    </div>
  );
}
