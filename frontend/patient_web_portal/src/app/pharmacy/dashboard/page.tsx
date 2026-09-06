"use client";

// Previously there was no pharmacist-facing section anywhere on the web
// portal — Header.tsx's navLinks had no PHARMACIST branch, and login.tsx's
// post-login redirect had no PHARMACIST case, so a pharmacist who signed in
// landed on the generic patient homepage with nothing to do. Meanwhile the
// mobile pharmacy app already has a full dashboard/stock/queue/alerts/
// profile set talking to the same /pharmacy/* backend — this section reuses
// those same endpoints for the web equivalent.

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Receipt, AlertTriangle, PackageX, CheckCircle2, Leaf, Store } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import api from '../../../lib/api';
import type { Prescription, PharmacyProfile } from '../../../types';
import { SkeletonList } from '../../../components/Skeleton';

interface Substitute { name: string; price: number }

function QueueCard({ item, onFulfilled }: { item: Prescription; onFulfilled: (id: number) => void }) {
  const [substitutes, setSubstitutes] = useState<Record<string, Substitute[]>>({});
  const [busy, setBusy] = useState(false);
  const [warnings, setWarnings] = useState<{ drug_a: string; drug_b: string; severity: string; description: string }[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (const med of item.medicines) {
        if (!med.name) continue;
        try {
          const res = await api.get<Substitute[]>('/pharmacy/substitutes', { params: { medicine: med.name } });
          if (!cancelled && res.data.length > 0) {
            setSubstitutes((prev) => ({ ...prev, [med.name]: res.data }));
          }
        } catch {
          // Substitute suggestions are a nice-to-have hint — never block the queue item on this.
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fulfill = async () => {
    if (!confirm('Mark this prescription as fulfilled? Stock will be decremented automatically.')) return;
    setBusy(true);
    try {
      const res = await api.put(`/pharmacy/fulfill/${item.id}`);
      const missing: string[] = res.data?.not_in_your_stock ?? [];
      const interactionWarnings = res.data?.interaction_warnings ?? [];
      if (missing.length > 0) {
        alert(`Fulfilled — but not in your stock: ${missing.join(', ')}`);
      }
      if (interactionWarnings.length > 0) {
        setWarnings(interactionWarnings);
        return; // onFulfilled fires once the pharmacist dismisses the warning dialog below.
      }
      onFulfilled(item.id);
    } catch {
      alert('Could not fulfill this prescription. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 font-bold text-lg">
          <Receipt size={18} className="text-emerald-500" /> #{item.id}
        </div>
        {item.diagnosis && (
          <span className="text-xs font-bold px-2 py-1 rounded-full bg-emerald-500/15 text-emerald-600">{item.diagnosis}</span>
        )}
      </div>

      <p className="text-sm font-semibold mb-2">Medicines needed</p>
      <ul className="space-y-1.5 mb-4">
        {item.medicines.map((m, i) => (
          <li key={i} className="text-sm">
            <span>• {m.name} — {m.dosage} ({m.frequency}, {m.duration})</span>
            {substitutes[m.name]?.length ? (
              <div className="flex items-center gap-1.5 mt-1 ml-3 text-xs text-emerald-600">
                <Leaf size={12} />
                Same-effect alternatives: {substitutes[m.name].map((s) => `${s.name} (₹${s.price})`).join(', ')}
              </div>
            ) : null}
          </li>
        ))}
      </ul>

      <button
        onClick={fulfill}
        disabled={busy}
        className="w-full py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl flex items-center justify-center gap-2 disabled:opacity-50 transition-colors"
      >
        <CheckCircle2 size={18} /> {busy ? 'Fulfilling…' : 'Fulfill'}
      </button>

      {warnings && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6" role="dialog" aria-modal="true">
          <div className="glass-panel p-6 max-w-md w-full">
            <div className="flex items-center gap-2 text-red-500 font-bold text-lg mb-3">
              <AlertTriangle /> Medicine Interaction Warning
            </div>
            <div className="space-y-2 mb-5 text-sm">
              {warnings.map((w, i) => (
                <p key={i}>{w.drug_a} + {w.drug_b} ({w.severity}): {w.description}</p>
              ))}
            </div>
            <button
              onClick={() => { setWarnings(null); onFulfilled(item.id); }}
              className="w-full py-2.5 bg-red-500 text-white font-bold rounded-xl"
            >
              I understand — mark fulfilled
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value, color, href }: { icon: React.ReactNode; label: string; value: number; color: string; href: string }) {
  const router = useRouter();
  return (
    <button onClick={() => router.push(href)} className="glass-panel p-5 text-left hover:scale-[1.02] transition-transform">
      <div className="mb-2" style={{ color }}>{icon}</div>
      <div className="text-3xl font-extrabold" style={{ color }}>{value}</div>
      <div className="text-sm text-gray-500">{label}</div>
    </button>
  );
}

export default function PharmacyDashboard() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [pharmacy, setPharmacy] = useState<PharmacyProfile | null>(null);
  const [queue, setQueue] = useState<Prescription[]>([]);
  const [expiringCount, setExpiringCount] = useState(0);
  const [lowStockCount, setLowStockCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [meRes, queueRes, expiringRes, stockRes] = await Promise.all([
        api.get<PharmacyProfile>('/pharmacy/me'),
        api.get<Prescription[]>('/pharmacy/queue'),
        api.get('/pharmacy/expiring'),
        api.get('/pharmacy/stock'),
      ]);
      setPharmacy(meRes.data);
      setQueue(queueRes.data);
      setExpiringCount(expiringRes.data.length);
      setLowStockCount(stockRes.data.filter((s: { status: string }) => s.status !== 'Optimal').length);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        // No Pharmacy entity registered yet for this account — send to setup
        // instead of showing a dead-end error.
        router.push('/pharmacy/profile');
        return;
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'PHARMACIST') {
      router.push('/');
      return;
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [user, authLoading, router, load]);

  if (authLoading || loading) {
    return (
      <div className="min-h-screen p-8 lg:p-24">
        <div className="glass-panel p-6"><SkeletonList count={4} /></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-24 relative overflow-hidden bg-[var(--background)]">
      <div className="absolute top-0 right-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[500px] h-[500px] bg-emerald-500 rounded-full mix-blend-multiply filter blur-[100px] opacity-10" />
      </div>

      <header className="flex flex-wrap justify-between items-center gap-4 mb-10">
        <div>
          <h1 className="text-4xl font-extrabold flex items-center gap-3">
            <Store className="text-emerald-500" size={36} /> {pharmacy?.name || 'My Pharmacy'}
          </h1>
          <p className="text-gray-500 mt-1">{pharmacy?.address || 'No address on file'}</p>
        </div>
        <button
          onClick={() => router.push('/pharmacy/profile')}
          className="neu-button px-5 py-2.5 font-bold rounded-xl"
        >
          Edit Profile
        </button>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-10">
        <StatCard icon={<Receipt size={26} />} label="Pending Orders" value={queue.length} color="#10b981" href="/pharmacy/dashboard" />
        <StatCard icon={<AlertTriangle size={26} />} label="Expiring Soon" value={expiringCount} color="#e8a33d" href="/pharmacy/stock?filter=expiring" />
        <StatCard icon={<PackageX size={26} />} label="Low / Out of Stock" value={lowStockCount} color="#d64545" href="/pharmacy/stock?filter=shortages" />
      </div>

      <h2 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Receipt className="text-emerald-500" /> Order Queue
      </h2>

      {queue.length === 0 ? (
        <div className="glass-panel p-10 text-center text-gray-500">No pending orders right now.</div>
      ) : (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {queue.map((item) => (
            <QueueCard key={item.id} item={item} onFulfilled={(id) => setQueue((q) => q.filter((p) => p.id !== id))} />
          ))}
        </motion.div>
      )}
    </div>
  );
}
