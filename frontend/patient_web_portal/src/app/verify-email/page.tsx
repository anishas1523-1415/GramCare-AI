"use client";

// Landing page for the link inside the verification email
// (FRONTEND_URL/verify-email?token=...). Registration and the email send
// both existed on the backend before this page did — clicking the link in
// a real verification email would have 404'd.

import React, { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import api from '../../lib/api';

function VerifyEmailInner() {
  const params = useSearchParams();
  const token = params.get('token');

  const [status, setStatus] = useState<'checking' | 'success' | 'error'>('checking');
  const [message, setMessage] = useState('');

  useEffect(() => {
    (async () => {
      if (!token) {
        setStatus('error');
        setMessage('This verification link is missing its token.');
        return;
      }
      try {
        await api.post('/auth/verify-email', { token });
        setStatus('success');
      } catch (err) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setStatus('error');
        setMessage(typeof detail === 'string' ? detail : 'This link is invalid or has expired.');
      }
    })();
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="glass-panel w-full max-w-md p-8 text-center">
        {status === 'checking' && (
          <>
            <Loader2 className="mx-auto mb-4 animate-spin text-indigo-500" size={40} />
            <p className="text-gray-500">Verifying your email…</p>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle2 className="mx-auto mb-4 text-emerald-500" size={44} />
            <h1 className="text-xl font-bold mb-2">Email verified</h1>
            <p className="text-gray-500 mb-6">You can now sign in to your account.</p>
            <a href="/login" className="neu-button inline-block px-6 py-3 bg-indigo-500 text-white font-bold rounded-xl">
              Go to Sign In
            </a>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="mx-auto mb-4 text-red-500" size={44} />
            <h1 className="text-xl font-bold mb-2">Verification failed</h1>
            <p className="text-gray-500 mb-6">{message}</p>
            <a href="/login" className="text-indigo-500 font-semibold hover:underline">Back to Sign In</a>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-gray-500">Loading…</div>}>
      <VerifyEmailInner />
    </Suspense>
  );
}
