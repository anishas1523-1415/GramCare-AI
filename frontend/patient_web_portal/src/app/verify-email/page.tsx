"use client";

// Landing page for the link inside the verification email
// (FRONTEND_URL/verify-email?token=...). Registration and the email send
// both existed on the backend before this page did — clicking the link in
// a real verification email would have 404'd.

import React, { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import api from '../../lib/api';
import { useLocale } from '../../contexts/LocaleContext';

function VerifyEmailInner() {
  const { t } = useLocale();
  const params = useSearchParams();
  const token = params.get('token');

  const [status, setStatus] = useState<'checking' | 'success' | 'error'>('checking');
  const [message, setMessage] = useState('');

  useEffect(() => {
    (async () => {
      if (!token) {
        setStatus('error');
        setMessage(t('verify_link_missing_token'));
        return;
      }
      try {
        await api.post('/auth/verify-email', { token });
        setStatus('success');
      } catch (err) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setStatus('error');
        setMessage(typeof detail === 'string' ? detail : t('verify_link_invalid'));
      }
    })();
  }, [token, t]);

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="glass-panel w-full max-w-md p-8 text-center">
        {status === 'checking' && (
          <>
            <Loader2 className="mx-auto mb-4 animate-spin text-indigo-500" size={40} />
            <p className="text-gray-500">{t('verifying_your_email')}</p>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle2 className="mx-auto mb-4 text-emerald-500" size={44} />
            <h1 className="text-xl font-bold mb-2">{t('email_verified')}</h1>
            <p className="text-gray-500 mb-6">{t('can_now_sign_in')}</p>
            <a href="/login" className="neu-button inline-block px-6 py-3 bg-indigo-500 text-white font-bold rounded-xl">
              {t('go_to_sign_in')}
            </a>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="mx-auto mb-4 text-red-500" size={44} />
            <h1 className="text-xl font-bold mb-2">{t('verification_failed')}</h1>
            <p className="text-gray-500 mb-6">{message}</p>
            <a href="/login" className="text-indigo-500 font-semibold hover:underline">{t('back_to_login')}</a>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  const { t } = useLocale();
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-gray-500">{t('loading_ellipsis')}</div>}>
      <VerifyEmailInner />
    </Suspense>
  );
}
