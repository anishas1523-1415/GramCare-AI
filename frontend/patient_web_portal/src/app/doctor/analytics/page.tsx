"use client";

// Community Health Intelligence — the planning doc's outbreak-cluster view
// for health authorities: anonymized clusters of similar AI-assessed
// conditions inside a time window, with alert flags on clusters that cross
// the outbreak threshold.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, AlertTriangle, Activity, Building2, Pill, Siren, CheckCircle2, Stethoscope, FileText, ThumbsUp, ThumbsDown, ShieldCheck } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import ThemedLoader from '../../../components/ThemedLoader';
import api from '../../../lib/api';

interface PendingDoctor {
  id: number;
  full_name: string;
  specialty: string;
  qualifications?: string | null;
  experience_years: number;
  languages?: string | null;
  license_number?: string | null;
  license_document_url?: string | null;
  service_hours?: string | null;
  verification_status: string;
}

/** Government doctor verification — the other missing half of the
 * anti-fake-doctor workflow: DoctorProfile.verification_status and the
 * approve/reject endpoints existed backend-only with no reviewer UI to
 * drive them, so no doctor could ever actually get approved through the
 * app. ADMIN-only, mirrors BatchRecallIssuer's placement/gating below. */
function DoctorVerificationPanel() {
  const [pending, setPending] = useState<PendingDoctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actingOn, setActingOn] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<PendingDoctor[]>('/doctors/pending');
        setPending(res.data);
      } catch {
        setError('Could not load pending doctor applications.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const approve = async (doctorId: number) => {
    setActingOn(doctorId);
    try {
      await api.put(`/doctors/${doctorId}/approve`);
      setPending((prev) => prev.filter((d) => d.id !== doctorId));
    } catch {
      setError('Could not approve this doctor.');
    } finally {
      setActingOn(null);
    }
  };

  const reject = async (doctorId: number) => {
    const reason = window.prompt('Reason for rejecting this application (shown to the doctor):');
    if (!reason || reason.trim().length < 3) return;
    setActingOn(doctorId);
    try {
      await api.put(`/doctors/${doctorId}/reject`, { reason: reason.trim() });
      setPending((prev) => prev.filter((d) => d.id !== doctorId));
    } catch {
      setError('Could not reject this doctor.');
    } finally {
      setActingOn(null);
    }
  };

  return (
    <div className="glass-panel p-6 mb-10">
      <h2 className="text-xl font-bold flex items-center gap-2 mb-1 text-indigo-500">
        <Stethoscope size={22} /> Doctor Verification Queue
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        A doctor is invisible to patients and blocked from prescriptions/appointments/SOS response until approved here.
      </p>
      {error && <p role="alert" className="text-red-500 text-sm font-semibold mb-3">{error}</p>}
      {loading ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : pending.length === 0 ? (
        <p className="text-sm text-gray-500">No applications waiting for review.</p>
      ) : (
        <div className="space-y-3">
          {pending.map((d) => (
            <div key={d.id} className="p-4 rounded-xl bg-white/40 dark:bg-black/30 border border-white/10">
              <div className="flex flex-wrap justify-between items-start gap-3">
                <div>
                  <h3 className="font-bold">{d.full_name}</h3>
                  <p className="text-sm text-gray-500">
                    {d.specialty}{d.qualifications ? ` · ${d.qualifications}` : ''} · {d.experience_years} yrs experience
                  </p>
                  {d.languages && <p className="text-xs text-gray-500">Speaks: {d.languages}</p>}
                  {d.service_hours && <p className="text-xs text-gray-500">Hours: {d.service_hours}</p>}
                  <p className="text-sm mt-1">
                    <strong>License #:</strong> {d.license_number || <span className="text-red-500">not provided</span>}
                  </p>
                  {d.license_document_url ? (
                    <a
                      href={d.license_document_url}
                      target="_blank" rel="noreferrer"
                      className="text-sm text-indigo-500 underline flex items-center gap-1 mt-1"
                    >
                      <FileText size={14} /> View license document
                    </a>
                  ) : (
                    <p className="text-xs text-red-500 mt-1">No license document uploaded</p>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    disabled={actingOn === d.id}
                    onClick={() => approve(d.id)}
                    className="px-3 py-2 bg-emerald-500 text-white rounded-lg text-sm font-bold flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <ThumbsUp size={15} /> Approve
                  </button>
                  <button
                    disabled={actingOn === d.id}
                    onClick={() => reject(d.id)}
                    className="px-3 py-2 border border-red-500/40 text-red-500 rounded-lg text-sm font-bold flex items-center gap-1.5 disabled:opacity-50 hover:bg-red-500/10"
                  >
                    <ThumbsDown size={15} /> Reject
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface IssuedRecall {
  id: number;
  medicine_name: string;
  batch_number: string;
  reason: string;
  created_at: string;
}

/** Batch Recall Alerts — health-authority-only (planning doc: "கவர்மெண்ட்
 * ஒரு மருந்து பேட்சை ரீகால் பண்ணா, பார்மசிஸ்ட்களும் யூசர்களும் உடனே அலர்ட்
 * ஆகணும்"). Pharmacists already receive matched recalls via
 * GET /pharmacy/recalls/mine — this is the missing other half: where an
 * authority actually issues one. */
function BatchRecallIssuer() {
  const [medicineName, setMedicineName] = useState('');
  const [batchNumber, setBatchNumber] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [issued, setIssued] = useState<IssuedRecall[]>([]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await api.post<IssuedRecall>('/pharmacy/recalls', {
        medicine_name: medicineName,
        batch_number: batchNumber,
        reason,
      });
      setIssued((prev) => [res.data, ...prev]);
      setMedicineName('');
      setBatchNumber('');
      setReason('');
    } catch {
      setError('Could not issue the recall. Please check the details and try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-6 mb-10">
      <h2 className="text-xl font-bold flex items-center gap-2 mb-1 text-red-500">
        <Siren size={22} /> Issue a Batch Recall
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        Pharmacists holding this batch are alerted immediately in their portal.
      </p>
      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
        <input
          required
          placeholder="Medicine name"
          value={medicineName}
          onChange={(e) => setMedicineName(e.target.value)}
          className="p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
        />
        <input
          required
          placeholder="Batch number"
          value={batchNumber}
          onChange={(e) => setBatchNumber(e.target.value)}
          className="p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
        />
        <input
          required
          placeholder="Reason (e.g. contamination found)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="md:col-span-3 neu-button py-3 bg-red-500 text-white font-bold rounded-xl disabled:opacity-50"
        >
          {busy ? 'Issuing…' : 'Issue Recall Alert'}
        </button>
      </form>
      {error && <p role="alert" className="text-red-500 text-sm font-semibold">{error}</p>}
      {issued.length > 0 && (
        <div className="mt-4 space-y-2">
          {issued.map((r) => (
            <div key={r.id} className="flex items-center gap-2 text-sm bg-red-500/10 border border-red-500/30 rounded-lg p-2">
              <CheckCircle2 size={16} className="text-red-500 shrink-0" />
              <span><strong>{r.medicine_name}</strong> (batch {r.batch_number}) — recall issued.</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface WhitelistEntry {
  id: number;
  email: string;
  note?: string | null;
  created_at: string;
}

/** Government Portal whitelist — the ONLY way to obtain an ADMIN account
 * (POST /auth/register/government) requires the caller's email to already
 * be in this table. Previously the sole way to add an entry was the
 * GOVERNMENT_WHITELIST_EMAILS env var, read once at backend startup —
 * meaning adding a single new government official required a Render
 * redeploy. This manages the table directly. ADMIN-only, same gating as
 * DoctorVerificationPanel/BatchRecallIssuer above. */
function GovernmentWhitelistPanel() {
  const [entries, setEntries] = useState<WhitelistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get<WhitelistEntry[]>('/auth/government-whitelist');
      setEntries(res.data);
    } catch {
      setError('Could not load the government whitelist.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.post('/auth/government-whitelist', { email, note: note || undefined });
      setEmail('');
      setNote('');
      await load();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Could not add this email.');
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm('Remove this email from the whitelist? They will no longer be able to register a Government Portal account with it.')) return;
    setBusy(true);
    setError('');
    try {
      await api.delete(`/auth/government-whitelist/${id}`);
      setEntries((prev) => prev.filter((e) => e.id !== id));
    } catch {
      setError('Could not remove this entry.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-6 mb-10">
      <h2 className="text-xl font-bold flex items-center gap-2 mb-1 text-purple-500">
        <ShieldCheck size={22} /> Government Portal Whitelist
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        Only emails listed here can register a Government Portal (Admin) account at /government/register.
      </p>

      <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-[2fr_2fr_auto] gap-3 mb-4">
        <input
          required
          type="email"
          placeholder="official@gov.example.in"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-purple-400 focus:outline-none"
        />
        <input
          placeholder="Note (optional — who/why)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-purple-400 focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="neu-button px-5 py-3 bg-purple-500 text-white font-bold rounded-xl disabled:opacity-50 whitespace-nowrap"
        >
          {busy ? 'Adding…' : 'Add Email'}
        </button>
      </form>

      {error && <p role="alert" className="text-red-500 text-sm font-semibold mb-3">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-500">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-gray-500">No whitelisted emails yet.</p>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between gap-3 p-3 rounded-xl bg-white/40 dark:bg-black/30 border border-white/10">
              <div>
                <p className="font-semibold text-sm">{entry.email}</p>
                {entry.note && <p className="text-xs text-gray-500">{entry.note}</p>}
              </div>
              <button
                disabled={busy}
                onClick={() => remove(entry.id)}
                className="text-xs font-bold text-red-500 hover:underline disabled:opacity-50 shrink-0"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface Cluster {
  condition: string;
  case_count: number;
  avg_severity: number;
  max_severity: number;
  first_seen: string;
  last_seen: string;
  alert: boolean;
}

interface Overview {
  window_days: number;
  total_assessments: number;
  critical_assessments: number;
  active_sos: number;
  unfulfilled_prescriptions: number;
  registered_pharmacies: number;
}

export default function HealthIntelligence() {
  const { user, loading: authLoading } = useAuth();
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [days, setDays] = useState(7);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !user) return;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const [c, o] = await Promise.all([
          api.get<Cluster[]>(`/analytics/health-clusters?days=${days}&min_cases=3`),
          api.get<Overview>(`/analytics/overview?days=${days}`),
        ]);
        setClusters(c.data);
        setOverview(o.data);
      } catch {
        setError('Not authorized or data unavailable (health-authority roles only).');
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, days]);

  const maxCount = Math.max(1, ...clusters.map((c) => c.case_count));

  return (
    <div className="min-h-screen p-8 lg:p-16 max-w-5xl mx-auto">
      <h1 className="text-4xl font-extrabold flex items-center gap-3 mb-2">
        <BarChart3 className="text-purple-500" size={40} /> Community Health Intelligence
      </h1>
      <p className="text-gray-500 mb-8">
        Anonymized symptom clusters across the region — early warning for disease spread.
      </p>

      <div className="flex gap-2 mb-8">
        {[7, 14, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-4 py-2 rounded-xl font-semibold text-sm ${days === d ? 'bg-purple-500 text-white' : 'bg-white/50 dark:bg-black/30'}`}
          >
            Last {d} days
          </button>
        ))}
      </div>

      {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

      {/* Doctor verification + recall issuance are health-authority actions,
          not clinician ones — this same component is shared with the
          Doctor analytics route, so both are gated to ADMIN accounts only. */}
      {user?.role === 'ADMIN' && <DoctorVerificationPanel />}
      {user?.role === 'ADMIN' && <GovernmentWhitelistPanel />}
      {user?.role === 'ADMIN' && <BatchRecallIssuer />}

      {loading ? (
        <ThemedLoader variant="analytics" />
      ) : (
        <>
          {overview && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
              {[
                { icon: Activity, label: 'AI assessments', value: overview.total_assessments, color: 'text-teal-500' },
                { icon: AlertTriangle, label: 'Critical cases', value: overview.critical_assessments, color: 'text-red-500' },
                { icon: Building2, label: 'Active SOS', value: overview.active_sos, color: 'text-orange-500' },
                { icon: Pill, label: 'Pending prescriptions', value: overview.unfulfilled_prescriptions, color: 'text-indigo-500' },
              ].map(({ icon: Icon, label, value, color }) => (
                <div key={label} className="glass-panel p-4 text-center">
                  <Icon className={`mx-auto mb-2 ${color}`} size={24} />
                  <div className="text-3xl font-extrabold">{value}</div>
                  <div className="text-xs text-gray-500">{label}</div>
                </div>
              ))}
            </div>
          )}

          <h2 className="text-xl font-bold mb-4">Condition clusters</h2>
          {clusters.length === 0 ? (
            <div className="glass-panel p-10 text-center text-gray-500">
              No symptom clusters in this window.
            </div>
          ) : (
            <div className="space-y-3">
              {clusters.map((c) => (
                <motion.div
                  key={c.condition}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`glass-panel p-4 ${c.alert ? 'border-l-8 border-l-red-500' : ''}`}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold capitalize">{c.condition}</span>
                    <span className="text-sm text-gray-500">
                      {c.case_count} case{c.case_count === 1 ? '' : 's'} · avg severity {c.avg_severity}
                      {c.alert && <span className="ml-2 px-2 py-0.5 bg-red-500 text-white rounded text-xs font-bold animate-pulse">CLUSTER ALERT</span>}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden">
                    <div
                      className={`h-full ${c.alert ? 'bg-red-500' : 'bg-purple-400'}`}
                      style={{ width: `${(c.case_count / maxCount) * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(c.first_seen).toLocaleDateString()} → {new Date(c.last_seen).toLocaleDateString()}
                  </p>
                </motion.div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
