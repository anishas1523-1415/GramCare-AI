"use client";

// "My Devices" — GET/DELETE /auth/sessions existed nowhere in the UI even
// after the backend gained the ability to list and revoke a session by ID.
// Previously the only way to end a session was /auth/logout with that
// device's own refresh token, so a lost or stolen phone could never be
// signed out remotely. Available to every logged-in role, not just one.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { Smartphone, MonitorSmartphone, ShieldOff } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import api from '../../../lib/api';

interface UserSession {
  id: number;
  device_info?: string | null;
  ip_address?: string | null;
  created_at: string;
  expires_at: string;
}

function describeDevice(ua?: string | null): string {
  if (!ua) return 'Unknown device';
  if (/android/i.test(ua)) return 'Android device';
  if (/iphone|ipad/i.test(ua)) return 'iOS device';
  if (/windows/i.test(ua)) return 'Windows — browser';
  if (/mac os/i.test(ua)) return 'Mac — browser';
  if (/linux/i.test(ua)) return 'Linux — browser';
  return ua.slice(0, 60);
}

export default function SessionsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revoking, setRevoking] = useState<number | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { router.push('/login'); return; }
    (async () => {
      try {
        const res = await api.get<UserSession[]>('/auth/sessions');
        setSessions(res.data);
      } catch {
        setError('Could not load your active sessions.');
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, router]);

  const revoke = async (id: number) => {
    setRevoking(id);
    setError('');
    try {
      await api.delete(`/auth/sessions/${id}`);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch {
      setError('Could not sign out that device.');
    } finally {
      setRevoking(null);
    }
  };

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading your devices…</div>;
  }

  return (
    <div className="min-h-screen p-8 lg:p-16 max-w-2xl mx-auto">
      <h1 className="text-3xl font-extrabold flex items-center gap-3 mb-2">
        <MonitorSmartphone className="text-teal-500" /> My Devices
      </h1>
      <p className="text-gray-500 mb-6">
        Every device currently signed in to your account. Lost your phone? Sign it out from here.
      </p>

      {error && <p role="alert" className="text-red-500 font-semibold mb-4">{error}</p>}

      {sessions.length === 0 ? (
        <div className="glass-panel p-8 text-center text-gray-500">No active sessions found.</div>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-panel p-4 flex items-center justify-between gap-4"
            >
              <div className="flex items-center gap-3 min-w-0">
                <Smartphone className="text-gray-400 shrink-0" size={22} />
                <div className="min-w-0">
                  <div className="font-bold truncate">{describeDevice(s.device_info)}</div>
                  <div className="text-xs text-gray-500">
                    {s.ip_address ? `${s.ip_address} · ` : ''}Signed in {new Date(s.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
              <button
                onClick={() => revoke(s.id)}
                disabled={revoking === s.id}
                className="neu-button px-3 py-2 text-sm font-bold rounded-xl flex items-center gap-2 text-red-500 disabled:opacity-50 shrink-0"
              >
                <ShieldOff size={15} /> {revoking === s.id ? 'Signing out…' : 'Sign out'}
              </button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
