"use client";

// Hospital Emergency Desk — the planning doc's central emergency portal:
// "இந்த SOS மெசேஜ் நேரா ஹாஸ்பிடல்ல இருக்கிற ஒரு சென்ட்ரல் எமர்ஜென்சி
// டெஸ்க்குத்தான் போகணும். அங்கிருக்கிற ஸ்டாப் இந்த அலர்ட்டை மானிட்டர்
// பண்ணி..." — a staffed desk monitors alerts, accepts them ("Help En
// Route"), and unanswered alerts escalate to the next hospital.
//
// Module theme: emergency red, pulse animation (per-module identity).

import React, { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Siren, MapPin, Mic, CheckCircle2, Clock, Ambulance, RefreshCw } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import api from '../../lib/api';
import { io } from 'socket.io-client';
import type { EmergencySOS } from '../../types';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "https://gramcare-signaling.onrender.com";

export default function HospitalEmergencyDesk() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [active, setActive] = useState<EmergencySOS[]>([]);
  const [responded, setResponded] = useState<EmergencySOS[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [live, setLive] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchSos = useCallback(async () => {
    try {
      const res = await api.get<EmergencySOS[]>('/sos/active');
      setActive(res.data);
      setLastUpdated(new Date());
      setError('');
    } catch {
      setError('Could not load emergencies (hospital/doctor accounts only).');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user || !['HOSPITAL', 'DOCTOR', 'ADMIN'].includes(user.role)) {
      router.push('/');
      return;
    }

    fetchSos();
    // Safety net alongside the socket: the desk must never silently go
    // stale during an emergency, even if the socket drops.
    const poll = setInterval(fetchSos, 30_000);

    const socket = io(WS_URL, {
      auth: { token: localStorage.getItem('access_token') },
    });
    socket.on('connect', () => {
      setLive(true);
      socket.emit('join_department', 'emergency_responders');
    });
    socket.on('disconnect', () => setLive(false));
    socket.on('emergency_alert', fetchSos);

    return () => {
      clearInterval(poll);
      socket.disconnect();
    };
  }, [user, authLoading, router, fetchSos]);

  const respond = async (sos: EmergencySOS) => {
    try {
      const res = await api.put<EmergencySOS>(`/sos/${sos.id}/respond`);
      setActive((prev) => prev.filter((s) => s.id !== sos.id));
      setResponded((prev) => [res.data, ...prev].slice(0, 10));
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Failed to acknowledge — it may already be handled.');
      fetchSos();
    }
  };

  const resolve = async (sos: EmergencySOS) => {
    try {
      await api.put(`/sos/${sos.id}/resolve`);
      setResponded((prev) => prev.filter((s) => s.id !== sos.id));
    } catch {
      setError('Failed to resolve.');
    }
  };

  const ageMinutes = (iso: string) =>
    Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading Emergency Desk…</div>;
  }

  return (
    <div className="min-h-screen p-6 lg:p-12 bg-[var(--background)]">
      {/* Emergency-red ambient */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-15%] right-[-10%] w-[480px] h-[480px] bg-red-500 rounded-full mix-blend-multiply filter blur-[110px] opacity-10" />
      </div>

      <header className="flex flex-wrap justify-between items-center gap-4 mb-10">
        <div>
          <h1 className="text-3xl lg:text-4xl font-extrabold flex items-center gap-3">
            <Siren className="text-red-500 animate-pulse" size={38} /> Emergency Desk
          </h1>
          <p className="text-gray-500 mt-1 flex items-center gap-3 text-sm">
            <span className={`flex items-center gap-1 font-bold ${live ? 'text-green-500' : 'text-red-500'}`}>
              ● {live ? 'Live feed connected' : 'Live feed offline — polling every 30s'}
            </span>
            {lastUpdated && <span>Updated {lastUpdated.toLocaleTimeString()}</span>}
          </p>
        </div>
        <button
          onClick={fetchSos}
          className="neu-button px-5 py-2 font-bold rounded-xl flex items-center gap-2"
        >
          <RefreshCw size={16} /> Refresh
        </button>
      </header>

      {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

      {/* ACTIVE — needs action NOW */}
      <section className="mb-12">
        <h2 className="text-xl font-bold text-red-600 mb-4">
          Incoming — awaiting acknowledgement ({active.length})
        </h2>
        {active.length === 0 ? (
          <div className="glass-panel p-10 text-center text-gray-500">
            No active emergencies. Stay ready.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {active.map((sos) => (
              <motion.div
                key={sos.id}
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                className="p-5 rounded-2xl bg-red-500/10 border-2 border-red-500/40 relative overflow-hidden"
              >
                <div className="flex justify-between items-start mb-3">
                  <span className="bg-red-500 text-white text-xs font-bold px-3 py-1 rounded-full animate-pulse">
                    {sos.severity}
                  </span>
                  <span className="flex items-center gap-1 text-xs font-bold text-red-700">
                    <Clock size={13} /> {ageMinutes(sos.created_at)} min ago
                  </span>
                </div>

                <h3 className="text-lg font-bold mb-1">Patient #{sos.patient_id}</h3>

                <p className="text-sm text-gray-700 dark:text-gray-200 flex items-center gap-1 mb-1">
                  <MapPin size={14} className="shrink-0" />
                  {sos.location_lat != null ? (
                    <a
                      className="underline font-semibold"
                      target="_blank" rel="noreferrer"
                      href={`https://maps.google.com/?q=${sos.location_lat},${sos.location_lng}`}
                    >
                      Open location in Maps
                    </a>
                  ) : (
                    sos.location_text || 'Location unknown'
                  )}
                </p>

                {sos.voice_note && (
                  <p className="text-sm italic flex items-start gap-1 mb-2 text-gray-800 dark:text-gray-100">
                    <Mic size={14} className="mt-0.5 shrink-0" /> &ldquo;{sos.voice_note}&rdquo;
                  </p>
                )}

                {(sos.escalation_level ?? 0) > 0 && (
                  <p className="text-xs font-bold text-orange-600 mb-2">
                    ⚠ Escalated ×{sos.escalation_level} — earlier hospital did not respond
                  </p>
                )}

                <button
                  onClick={() => respond(sos)}
                  className="w-full mt-2 py-3 bg-red-600 hover:bg-red-700 text-white font-extrabold rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <Ambulance size={18} /> ACKNOWLEDGE — HELP EN ROUTE
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </section>

      {/* RESPONDED — help en route, resolve on arrival */}
      <section>
        <h2 className="text-xl font-bold text-emerald-600 mb-4">
          Help en route — this desk ({responded.length})
        </h2>
        {responded.length === 0 ? (
          <p className="text-gray-500 text-sm">
            Emergencies you acknowledge appear here until resolved.
          </p>
        ) : (
          <div className="space-y-3 max-w-3xl">
            {responded.map((sos) => (
              <div key={sos.id} className="glass-panel p-4 flex items-center justify-between border-l-8 border-l-emerald-500">
                <div>
                  <span className="font-bold">Patient #{sos.patient_id}</span>
                  <span className="text-sm text-gray-500 ml-3">
                    acknowledged {new Date().toLocaleTimeString()}
                  </span>
                </div>
                <button
                  onClick={() => resolve(sos)}
                  className="px-4 py-2 border border-emerald-500 text-emerald-600 hover:bg-emerald-500 hover:text-white rounded-lg font-bold text-sm transition-colors flex items-center gap-1"
                >
                  <CheckCircle2 size={16} /> Mark resolved
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
