"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Users, Calendar, ShieldAlert, Video, FileText, CheckCircle, Clock, Plus, Trash2, Brain, BarChart3, AlertTriangle, Share2 } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import api from '../../../lib/api';
import { io } from 'socket.io-client';
import type { Slot, Appointment, EmergencySOS, Referral } from '../../../types';
import { APIProvider, Map, Marker } from '@vis.gl/react-google-maps';
import { SkeletonList } from '../../../components/Skeleton';

interface AssistSummary {
  patient_name: string;
  risk_flag: 'LOW' | 'MODERATE' | 'HIGH';
  summary_text: string;
  active_medicines: { name: string; dosage: string; days_remaining: number }[];
  recent_conditions: string[];
  latest_vitals?: { heart_rate: number; spo2: number; temperature: number } | null;
  generated_by: string;
}

/** AI Doctor Assistant panel — the planning doc's pre-consultation summary
 * ("டாக்டர்ஸ் பேஷன்ட்ட பாக்குறதுக்கு முன்னாடியே... சம்மரி ரிப்போர்ட்"). */
function AssistPanel({ patientId, familyProfileId }: { patientId: number; familyProfileId?: number | null }) {
  const [summary, setSummary] = useState<AssistSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const load = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (summary) return;
    setLoading(true);
    try {
      const res = await api.get<AssistSummary>(`/assist/patient-summary/${patientId}`, {
        params: familyProfileId ? { family_profile_id: familyProfileId } : {},
      });
      setSummary(res.data);
    } catch {
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full">
      <button
        onClick={load}
        className="mt-2 flex items-center gap-2 text-sm font-semibold text-purple-600 hover:text-purple-800"
      >
        <Brain size={16} /> {open ? 'Hide AI summary' : 'AI pre-consult summary'}
      </button>
      {open && (
        <div className="mt-2 p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-sm">
          {loading ? (
            <span className="text-gray-500">Preparing summary…</span>
          ) : summary ? (
            <>
              <div className="flex items-center gap-2 mb-1">
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${summary.risk_flag === 'HIGH' ? 'bg-red-500 text-white' : summary.risk_flag === 'MODERATE' ? 'bg-yellow-500 text-black' : 'bg-green-500 text-white'}`}>
                  {summary.risk_flag} RISK
                </span>
                <span className="text-xs text-gray-500">({summary.generated_by})</span>
              </div>
              <p className="mb-2">{summary.summary_text}</p>
              {summary.active_medicines.length > 0 && (
                <p className="text-xs text-gray-600">
                  <strong>Active medicines:</strong>{' '}
                  {summary.active_medicines.map((m) => `${m.name} (${m.days_remaining}d left)`).join(', ')}
                </p>
              )}
              {summary.latest_vitals && (
                <p className="text-xs text-gray-600">
                  <strong>Latest vitals:</strong> HR {summary.latest_vitals.heart_rate}, SpO2 {summary.latest_vitals.spo2}%, {summary.latest_vitals.temperature}°C
                </p>
              )}
            </>
          ) : (
            <span className="text-gray-500">No summary available for this patient.</span>
          )}
        </div>
      )}
    </div>
  );
}

/** Doctor availability editor — publishes the slots patients book against
 * (planning doc: bookings only happen inside the doctor's published
 * calendar). */
function SlotManager({ doctorId }: { doctorId: number }) {
  const [slots, setSlots] = useState<Slot[]>([]);
  const [newStart, setNewStart] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get<Slot[]>(`/doctors/${doctorId}/slots`, {
        params: { include_booked: true },
      });
      setSlots(res.data);
    } catch {
      setError('Could not load your schedule.');
    }
  }, [doctorId]);

  useEffect(() => {
    (async () => { await load(); })();
  }, [load]);

  const addSlot = async () => {
    if (!newStart) return;
    setBusy(true);
    setError('');
    try {
      const start = new Date(newStart);
      const end = new Date(start.getTime() + 30 * 60 * 1000); // 30-min consults
      await api.post('/doctors/me/slots', [
        { start_time: start.toISOString(), end_time: end.toISOString() },
      ]);
      setNewStart('');
      await load();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Could not publish the slot.');
    } finally {
      setBusy(false);
    }
  };

  const removeSlot = async (id: number) => {
    try {
      await api.delete(`/doctors/me/slots/${id}`);
      await load();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Could not remove the slot.');
    }
  };

  return (
    <div className="neu-panel p-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <Clock className="text-teal-500" /> My Availability
      </h2>
      {error && <p role="alert" className="text-red-500 text-sm font-semibold mb-3">{error}</p>}

      <div className="flex gap-2 mb-4">
        <input
          type="datetime-local"
          value={newStart}
          onChange={(e) => setNewStart(e.target.value)}
          aria-label="New slot start time"
          className="flex-1 p-2 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm"
        />
        <button
          onClick={addSlot}
          disabled={busy || !newStart}
          aria-label="Publish slot"
          className="px-3 py-2 bg-teal-500 text-white rounded-lg disabled:opacity-40"
        >
          <Plus size={18} />
        </button>
      </div>

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {slots.length === 0 ? (
          <p className="text-sm text-gray-500">No published slots. Patients cannot book you until you add some.</p>
        ) : (
          slots.map((s) => (
            <div key={s.id} className="flex items-center justify-between p-2 rounded-lg bg-white/40 dark:bg-black/30 text-sm">
              <span>
                {new Date(s.start_time).toLocaleString(undefined, {
                  weekday: 'short', day: 'numeric', month: 'short',
                  hour: '2-digit', minute: '2-digit',
                })}
              </span>
              {s.is_booked ? (
                <span className="text-xs font-bold text-indigo-500 bg-indigo-500/10 px-2 py-1 rounded">Booked</span>
              ) : (
                <button
                  onClick={() => removeSlot(s.id)}
                  aria-label="Remove slot"
                  className="text-gray-400 hover:text-red-500"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

const REFERRAL_STATUS_STYLE: Record<Referral['status'], string> = {
  PENDING: 'bg-amber-500/15 text-amber-500 border-amber-500/30',
  ACCEPTED: 'bg-teal-500/15 text-teal-500 border-teal-500/30',
  DECLINED: 'bg-red-500/15 text-red-500 border-red-500/30',
  COMPLETED: 'bg-emerald-500/15 text-emerald-500 border-emerald-500/30',
};

/** Referral Network panel (planning-doc feature: a doctor can hand a
 * patient off to a colleague, or open the referral to any doctor of a
 * target specialty). Shows both directions — referrals waiting on this
 * doctor to act, and ones this doctor has sent out. */
function ReferralsPanel({ doctorId }: { doctorId: number }) {
  const [tab, setTab] = useState<'incoming' | 'sent'>('incoming');
  const [incoming, setIncoming] = useState<Referral[]>([]);
  const [sent, setSent] = useState<Referral[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [incRes, sentRes] = await Promise.all([
        api.get<Referral[]>('/referrals/incoming'),
        api.get<Referral[]>('/referrals/sent'),
      ]);
      setIncoming(incRes.data);
      setSent(sentRes.data);
    } catch {
      setError('Could not load referrals.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const act = async (id: number, action: 'accept' | 'decline' | 'complete') => {
    setBusyId(id);
    setError('');
    try {
      await api.put(`/referrals/${id}/${action}`);
      await load();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Could not update this referral.');
    } finally {
      setBusyId(null);
    }
  };

  const list = tab === 'incoming' ? incoming : sent;

  return (
    <div className="neu-panel p-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <Share2 className="text-indigo-500" /> Referrals
      </h2>

      <div className="flex gap-2 mb-4">
        <button
          type="button"
          onClick={() => setTab('incoming')}
          className={`flex-1 py-2 rounded-lg text-sm font-bold transition-colors ${tab === 'incoming' ? 'bg-indigo-500 text-white' : 'bg-white/40 dark:bg-black/20'}`}
        >
          Incoming{incoming.length > 0 ? ` (${incoming.length})` : ''}
        </button>
        <button
          type="button"
          onClick={() => setTab('sent')}
          className={`flex-1 py-2 rounded-lg text-sm font-bold transition-colors ${tab === 'sent' ? 'bg-indigo-500 text-white' : 'bg-white/40 dark:bg-black/20'}`}
        >
          Sent
        </button>
      </div>

      {error && <p role="alert" className="text-red-500 text-sm font-semibold mb-3">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-500 text-center py-6">Loading…</p>
      ) : list.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-6">
          {tab === 'incoming' ? 'No referrals waiting on you.' : "Referrals you've sent will appear here."}
        </p>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
          {list.map((r) => (
            <div key={r.id} className="p-3 rounded-xl bg-white/40 dark:bg-black/30 border border-white/20 text-sm">
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="font-bold">{r.specialty}</span>
                <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-bold border ${REFERRAL_STATUS_STYLE[r.status]}`}>
                  {r.status}
                </span>
              </div>
              <p className="text-xs text-gray-500 mb-1">Patient #{r.patient_id}</p>
              <p className="text-xs text-gray-600 dark:text-gray-300 mb-2">{r.reason}</p>
              {!r.referred_to_doctor_id && r.status === 'PENDING' && (
                <p className="text-xs text-indigo-500 font-semibold mb-2">Open referral — accepting claims it</p>
              )}
              {tab === 'incoming' && r.status === 'PENDING' && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busyId === r.id}
                    onClick={() => act(r.id, 'accept')}
                    className="flex-1 py-1.5 bg-teal-500 text-white rounded-lg text-xs font-bold disabled:opacity-50"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    disabled={busyId === r.id}
                    onClick={() => act(r.id, 'decline')}
                    className="flex-1 py-1.5 bg-red-500 text-white rounded-lg text-xs font-bold disabled:opacity-50"
                  >
                    Decline
                  </button>
                </div>
              )}
              {tab === 'incoming' && r.status === 'ACCEPTED' && r.referred_to_doctor_id === doctorId && (
                <button
                  type="button"
                  disabled={busyId === r.id}
                  onClick={() => act(r.id, 'complete')}
                  className="w-full py-1.5 bg-emerald-500 text-white rounded-lg text-xs font-bold disabled:opacity-50"
                >
                  Mark Complete
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DoctorDashboard() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [activeSOS, setActiveSOS] = useState<EmergencySOS[]>([]);
  const [loading, setLoading] = useState(true);
  const [socketConnected, setSocketConnected] = useState(false);
  // Government verification gate: a doctor account works the moment it's
  // registered, but is PENDING until a government reviewer approves it —
  // the backend blocks the queue/SOS-response endpoints for anyone not
  // APPROVED (require_approved_doctor), so this dashboard must know that
  // state up front rather than let those calls silently 403.
  const [verificationStatus, setVerificationStatus] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;

    // Redirect non-doctors
    if (!user || user.role !== "DOCTOR") {
      router.push("/");
      return;
    }

    const fetchData = async () => {
      try {
        const me = await api.get('/doctors/me');
        setVerificationStatus(me.data.verification_status);
        setRejectionReason(me.data.rejection_reason ?? null);

        if (me.data.verification_status !== 'APPROVED') {
          setLoading(false);
          return;
        }

        // Fetch queue and SOS from actual backend.
        // Previously hardcoded to 2 regardless of who was logged in — the
        // backend's GET /appointments/doctor/{doctor_id}/queue rejects the
        // request with 403 for any doctor whose real id isn't 2, so this
        // was breaking the dashboard for every other doctor account. Now
        // uses the authenticated doctor's real id (guaranteed non-null here
        // since the effect already redirects non-doctors above).
        const doctorId = user!.id;
        const [queueRes, sosRes] = await Promise.all([
          api.get(`/appointments/doctor/${doctorId}/queue`),
          api.get('/sos/active')
        ]);

        setAppointments(queueRes.data);
        setActiveSOS(sosRes.data);
      } catch (error) {
        console.error("Failed to fetch doctor data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();

    // Setup real-time listeners for new SOS or triage alerts.
    // The Node signaling server now requires a valid JWT to join a
    // department room (join_department) — pass the same access token used
    // for REST calls so this doctor's socket is recognized as authenticated.
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "https://gramcare-signaling.onrender.com";
    const socket = io(WS_URL, {
      auth: { token: localStorage.getItem('access_token') },
    });

    socket.on("connect", () => {
      setSocketConnected(true);
      socket.emit("join_department", "General Medicine");
      // Scoped SOS delivery: responders join this room instead of relying
      // on a global broadcast to every connected socket.
      socket.emit("join_department", "emergency_responders");
    });

    socket.on("disconnect", () => setSocketConnected(false));

    socket.on("emergency_alert", () => {
      // Refresh active SOS list
      fetchData();
    });

    return () => {
      socket.disconnect();
    };
  }, [user, authLoading, router]);

  const respondToSOS = async (sosId: number) => {
    try {
      await api.put(`/sos/${sosId}/respond`);
      setActiveSOS(activeSOS.filter(sos => sos.id !== sosId));
      alert("You have responded to the SOS. Routing to patient location...");
    } catch {
      alert("Failed to respond to SOS.");
    }
  };

  const completeAppointment = async (apptId: number) => {
    try {
      await api.put(`/appointments/${apptId}`, { status: "COMPLETED" });
      setAppointments(appointments.filter(app => app.id !== apptId));
    } catch {
      alert("Failed to complete appointment.");
    }
  };

  if (authLoading) {
    return <div className="min-h-screen flex items-center justify-center">Loading Doctor Portal...</div>;
  }

  if (loading) {
    return (
      <div className="min-h-screen p-8 lg:p-24">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <div className="glass-panel p-6">
              <SkeletonList count={4} />
            </div>
          </div>
          <div className="glass-panel p-6">
            <SkeletonList count={2} />
          </div>
        </div>
      </div>
    );
  }

  // Government verification gate — a PENDING/REJECTED doctor never reaches
  // the queue/SOS-response UI below (the backend would 403 those calls
  // anyway); show them a clear status screen instead.
  if (verificationStatus && verificationStatus !== 'APPROVED') {
    const isRejected = verificationStatus === 'REJECTED';
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-panel p-10 max-w-lg text-center"
        >
          {isRejected ? (
            <AlertTriangle className="mx-auto mb-4 text-red-500" size={48} />
          ) : (
            <Clock className="mx-auto mb-4 text-amber-500" size={48} />
          )}
          <h1 className="text-2xl font-bold mb-2">
            {isRejected ? 'Application Not Approved' : 'Application Under Review'}
          </h1>
          <p className="text-gray-500 mb-4">
            {isRejected
              ? 'Your doctor account was not approved by the government reviewer.'
              : 'Your doctor account is pending government verification. You’ll be notified by email once it’s reviewed, and can log in normally after approval.'}
          </p>
          {isRejected && rejectionReason && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-sm text-left mb-4">
              <strong>Reason:</strong> {rejectionReason}
            </div>
          )}
          <p className="text-sm text-gray-500">
            You can still update your profile details (specialty, qualifications, license number,
            and license document) from{' '}
            <a href="/doctor/profile" className="underline text-indigo-500">your profile page</a>{' '}
            {isRejected ? 'and resubmit for review.' : 'while you wait.'}
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-24 relative overflow-hidden bg-[var(--background)]">
      {/* Background elements */}
      <div className="absolute top-0 right-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] bg-teal-500 rounded-full mix-blend-multiply filter blur-[100px] opacity-10" />
      </div>

      <header className="flex justify-between items-center mb-12">
        <div>
          <h1 className="text-4xl font-extrabold">Welcome, Dr. {user?.username}</h1>
          <p className="text-gray-500 mt-1 flex items-center gap-2">
            Status: {socketConnected ? <span className="text-green-500 font-bold">Online</span> : <span className="text-red-500 font-bold">Offline</span>}
          </p>
        </div>
        <div className="flex gap-4">
          <button
            onClick={() => router.push('/doctor/analytics')}
            className="neu-button px-6 py-2 bg-purple-500 text-white font-bold rounded-xl flex items-center gap-2"
          >
            <BarChart3 size={20} /> Health Intelligence
          </button>
        </div>
      </header>

      {/* Active Emergencies (High Priority) */}
      {activeSOS.length > 0 && (
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-12">
          <h2 className="text-2xl font-bold text-red-500 mb-6 flex items-center gap-2">
            <ShieldAlert className="animate-pulse" /> Active Emergencies
          </h2>

          <div className="mb-6 rounded-2xl overflow-hidden border border-red-500/30 h-[300px] w-full">
            <APIProvider apiKey={process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || ""}>
              <Map
                defaultZoom={12}
                defaultCenter={
                  activeSOS.length > 0 && activeSOS[0].location_lat != null && activeSOS[0].location_lng != null
                  ? { lat: activeSOS[0].location_lat, lng: activeSOS[0].location_lng }
                  : { lat: 12.9716, lng: 77.5946 }
                }
                mapId="sos_map"
                gestureHandling={'greedy'}
                disableDefaultUI={true}
              >
                {activeSOS.map(sos => (
                  sos.location_lat != null && sos.location_lng != null ? (
                    <Marker
                      key={`marker-${sos.id}`}
                      position={{ lat: sos.location_lat, lng: sos.location_lng }}
                    />
                  ) : null
                ))}
              </Map>
            </APIProvider>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {activeSOS.map(sos => (
              <div key={sos.id} className="bg-red-500/10 border border-red-500/30 p-6 rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4">
                  <span className="bg-red-500 text-white text-xs font-bold px-3 py-1 rounded-full animate-pulse">CRITICAL</span>
                </div>
                <h3 className="text-xl font-bold mb-2">SOS from Patient #{sos.patient_id}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-300 mb-1">
                  Location: {sos.location_lat != null
                    ? <a className="underline" target="_blank" rel="noreferrer" href={`https://maps.google.com/?q=${sos.location_lat},${sos.location_lng}`}>{sos.location_lat}, {sos.location_lng}</a>
                    : (sos.location_text || 'Unknown')}
                </p>
                {sos.voice_note && (
                  <p className="text-sm italic text-gray-700 dark:text-gray-200 mb-1">&ldquo;{sos.voice_note}&rdquo;</p>
                )}
                {(sos.escalation_level ?? 0) > 0 && (
                  <p className="text-xs font-bold text-orange-600 mb-1">Escalated ×{sos.escalation_level} (unanswered)</p>
                )}
                <p className="text-xs text-gray-500 mb-6">Triggered at: {new Date(sos.created_at).toLocaleTimeString()}</p>
                <button
                  onClick={() => respondToSOS(sos.id)}
                  className="w-full py-3 bg-red-500 hover:bg-red-600 text-white font-bold rounded-xl transition-colors"
                >
                  Acknowledge & Respond
                </button>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Appointment Queue */}
        <div className="lg:col-span-2">
          <h2 className="text-2xl font-bold mb-6 flex items-center gap-2"><Calendar className="text-teal-500" /> Patient Queue</h2>

          <div className="glass-panel p-6">
            {appointments.length === 0 ? (
              <div className="text-center p-10 text-gray-500">No upcoming appointments.</div>
            ) : (
              <div className="space-y-4">
                {appointments.map((appt) => (
                  <div key={appt.id} className="flex flex-col md:flex-row justify-between items-start md:items-center p-4 bg-white/40 dark:bg-black/40 border border-white/20 rounded-xl">
                    <div className="mb-4 md:mb-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="font-bold text-lg">Patient #{appt.patient_id}</h3>
                        <span className="text-xs font-bold bg-teal-500/20 text-teal-500 px-2 py-1 rounded">{appt.status}</span>
                        {/* Predictive Risk Stratification (planning doc): the
                            queue itself is already severity-sorted server-side —
                            this badge makes that ordering visible/explainable. */}
                        {appt.triage_severity_score != null && appt.triage_severity_score >= 50 && (
                          <span className={`text-xs font-bold px-2 py-1 rounded flex items-center gap-1 ${
                            appt.triage_severity_score >= 75
                              ? 'bg-red-500 text-white animate-pulse'
                              : 'bg-orange-500 text-white'
                          }`}>
                            <AlertTriangle size={12} /> Risk {appt.triage_severity_score}/100
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500">Scheduled: {new Date(appt.scheduled_at).toLocaleString()}</p>
                      {appt.triage_summary && <p className="text-sm mt-2 text-gray-600 dark:text-gray-300"><strong>Triage:</strong> {appt.triage_summary}</p>}
                      <AssistPanel patientId={appt.patient_id} familyProfileId={appt.family_profile_id} />
                    </div>

                    <div className="flex gap-2 w-full md:w-auto">
                      <button
                        onClick={() => router.push(`/consultation/${appt.id}`)}
                        className="flex-1 md:flex-none px-4 py-2 bg-indigo-500 text-white rounded-lg flex items-center justify-center gap-2 text-sm font-semibold hover:bg-indigo-600 transition-colors"
                      >
                        <Video size={16} /> Consult
                      </button>
                      <button
                        onClick={() => router.push(`/doctor/prescription/${appt.id}?patient_id=${appt.patient_id}`)}
                        className="flex-1 md:flex-none px-4 py-2 bg-teal-500 text-white rounded-lg flex items-center justify-center gap-2 text-sm font-semibold hover:bg-teal-600 transition-colors"
                      >
                        <FileText size={16} /> Write Rx
                      </button>
                      <button
                        onClick={() => completeAppointment(appt.id)}
                        className="p-2 border border-green-500 text-green-500 rounded-lg flex items-center justify-center hover:bg-green-500 hover:text-white transition-colors"
                        title="Mark Completed"
                      >
                        <CheckCircle size={20} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-8">
          {user?.id != null && <SlotManager doctorId={user.id} />}
          {user?.id != null && <ReferralsPanel doctorId={user.id} />}

          <div className="neu-panel p-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2"><Users className="text-indigo-500" /> Patient Directory</h2>
            <p className="text-sm text-gray-500 mb-4">Recent patient records across the network.</p>
            <button
              onClick={() => router.push('/doctor/directory')}
              className="w-full py-3 bg-indigo-500 text-white font-bold rounded-xl hover:bg-indigo-600 transition-colors"
            >
              View Directory
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
