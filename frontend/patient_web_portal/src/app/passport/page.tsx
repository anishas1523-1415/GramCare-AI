"use client";

// Digital Health Passport — a patient's own emergency-response profile
// (blood group, allergies, chronic conditions) plus a QR code linking to
// the public, no-login view of it. The public view exists specifically so
// an EMT or hospital desk with no GramCare account can read it by
// scanning a phone/wristband — see /passport/view/[token] and
// modules/passport/router.py.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import QRCode from 'qrcode';
import { Stethoscope, ShieldCheck, RefreshCw, Copy, Check, Download } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useProfile } from '../../contexts/ProfileContext';
import { useRouter } from 'next/navigation';
import api from '../../lib/api';

interface PassportSelf {
  full_name: string;
  blood_group?: string | null;
  allergies?: string | null;
  chronic_conditions?: string | null;
  passport_token?: string | null;
}

export default function HealthPassportPage() {
  const { user, loading: authLoading } = useAuth();
  const { profiles, activeProfile, setActiveProfile } = useProfile();
  const router = useRouter();

  const [passport, setPassport] = useState<PassportSelf | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'PATIENT') {
      router.push('/');
      return;
    }
    (async () => {
      try {
        const res = await api.get<PassportSelf>('/passport/me');
        setPassport(res.data);
      } catch {
        setError('Could not load your health passport.');
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, router]);

  const passportUrl = (token: string) =>
    `${window.location.origin}/passport/view/${token}`;

  useEffect(() => {
    if (!passport?.passport_token) {
      void Promise.resolve().then(() => setQrDataUrl(''));
      return;
    }
    QRCode.toDataURL(passportUrl(passport.passport_token), { width: 240, margin: 1 })
      .then(setQrDataUrl)
      .catch(() => setQrDataUrl(''));
  }, [passport?.passport_token]);

  const field = (key: keyof PassportSelf, value: string) => {
    setPassport((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passport) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.put<PassportSelf>('/passport/me', {
        blood_group: passport.blood_group || undefined,
        allergies: passport.allergies || undefined,
        chronic_conditions: passport.chronic_conditions || undefined,
      });
      setPassport(res.data);
      setSuccess('Health passport saved.');
    } catch {
      setError('Could not save your health passport.');
    } finally {
      setSaving(false);
    }
  };

  const regenerate = async () => {
    if (!window.confirm('This makes any previously printed or shared QR code stop working. Continue?')) return;
    setRegenerating(true);
    setError('');
    try {
      const res = await api.post<PassportSelf>('/passport/me/regenerate-token');
      setPassport(res.data);
      setSuccess('New QR code generated — the old one no longer works.');
    } catch {
      setError('Could not regenerate your QR code.');
    } finally {
      setRegenerating(false);
    }
  };

  const copyLink = async () => {
    if (!passport?.passport_token) return;
    await navigator.clipboard.writeText(passportUrl(passport.passport_token));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadFhirExport = async () => {
    setExporting(true);
    setError('');
    try {
      const res = await api.get('/ehr/fhir-export', {
        params: { family_profile_id: activeProfile?.id ?? undefined },
        responseType: 'blob',
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'gramcare_health_records_fhir.json';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError('Could not export health records.');
    } finally {
      setExporting(false);
    }
  };

  if (authLoading || loading || !passport) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading your health passport…</div>;
  }

  return (
    <div className="min-h-screen p-8 lg:p-16 max-w-3xl mx-auto">
      <h1 className="text-3xl font-extrabold flex items-center gap-3 mb-2">
        <ShieldCheck className="text-red-500" /> Digital Health Passport
      </h1>
      <p className="text-gray-500 mb-6">
        A QR code for your blood group, allergies, and conditions — readable by an EMT or hospital
        desk without needing to log in. Keep it in your wallet or as a phone lock-screen photo.
      </p>

      {error && <p role="alert" className="text-red-500 font-semibold mb-4">{error}</p>}
      {success && <p role="status" className="text-emerald-500 font-semibold mb-4">{success}</p>}

      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 mb-6">
        <form onSubmit={save} className="glass-panel p-6 space-y-4">
          <div>
            <label htmlFor="passport-blood-group" className="block text-sm font-semibold mb-1.5">Blood Group</label>
            <input
              id="passport-blood-group"
              value={passport.blood_group ?? ''}
              onChange={(e) => field('blood_group', e.target.value)}
              placeholder="e.g. O+"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="passport-allergies" className="block text-sm font-semibold mb-1.5">Allergies</label>
            <textarea
              id="passport-allergies"
              value={passport.allergies ?? ''}
              onChange={(e) => field('allergies', e.target.value)}
              rows={2}
              placeholder="e.g. Penicillin, peanuts"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="passport-conditions" className="block text-sm font-semibold mb-1.5">Chronic Conditions</label>
            <textarea
              id="passport-conditions"
              value={passport.chronic_conditions ?? ''}
              onChange={(e) => field('chronic_conditions', e.target.value)}
              rows={2}
              placeholder="e.g. Type 2 diabetes, asthma"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={saving}
            className="neu-button px-5 py-3 bg-red-500 text-white font-bold rounded-xl disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save Passport'}
          </button>
        </form>

        <div className="glass-panel p-6 flex flex-col items-center justify-center gap-4 text-center">
          {qrDataUrl ? (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={qrDataUrl} alt="Your Health Passport QR code" className="w-48 h-48 rounded-lg bg-white p-2" />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={copyLink}
                  className="neu-button px-3 py-2 text-xs font-bold rounded-lg flex items-center gap-1.5"
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? 'Copied' : 'Copy Link'}
                </button>
                <button
                  type="button"
                  onClick={regenerate}
                  disabled={regenerating}
                  className="neu-button px-3 py-2 text-xs font-bold rounded-lg flex items-center gap-1.5 text-red-500 disabled:opacity-50"
                >
                  <RefreshCw size={14} /> {regenerating ? 'Regenerating…' : 'New Code'}
                </button>
              </div>
            </>
          ) : (
            <div className="text-sm text-gray-500 flex flex-col items-center gap-2">
              <Stethoscope size={32} className="text-gray-400" />
              Save the form to generate your QR code.
            </div>
          )}
        </div>
      </div>

      <div className="glass-panel p-6 mb-6">
        <h2 className="text-lg font-bold mb-1.5 flex items-center gap-2">
          <Download size={18} className="text-indigo-500" /> Export Health Records
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          Download your full Family Health Wallet — prescriptions, lab reports, vaccinations, and
          notes — as a FHIR-shaped file a receiving hospital or clinic&apos;s EHR system can read.
        </p>
        {profiles.length > 0 && (
          <div className="mb-4 max-w-xs">
            <label htmlFor="passport-export-profile" className="text-sm font-semibold block mb-1.5">For</label>
            <select
              id="passport-export-profile"
              value={activeProfile?.id ?? ''}
              onChange={(e) => {
                const id = e.target.value;
                setActiveProfile(id === '' ? null : profiles.find((p) => p.id === Number(id)) || null);
              }}
              className="w-full p-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option value="">Myself</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.full_name} ({p.relation})</option>
              ))}
            </select>
          </div>
        )}
        <button
          type="button"
          onClick={downloadFhirExport}
          disabled={exporting}
          className="neu-button px-5 py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-50 flex items-center gap-2"
        >
          <Download size={16} /> {exporting ? 'Preparing…' : 'Download (FHIR JSON)'}
        </button>
      </div>

      <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-xs text-gray-400 text-center">
        Anyone with this QR code or link can see your blood group, allergies, conditions, and
        emergency contacts — no password needed. That&apos;s the point in an emergency, but keep the
        code itself private otherwise, and use &quot;New Code&quot; if you ever lose it.
      </motion.p>
    </div>
  );
}
