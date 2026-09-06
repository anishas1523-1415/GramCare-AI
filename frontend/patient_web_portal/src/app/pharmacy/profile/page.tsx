"use client";

// Pharmacy profile — doubles as one-time onboarding. Every /pharmacy/*
// endpoint (queue, stock, expiring, me itself) looks up a Pharmacy row by
// the account's owner_user_id and 409s ("No pharmacy registered for this
// account yet") until POST /pharmacy/register has been called once. That
// endpoint upserts (see modules/pharmacy_inventory/router.py's
// register_pharmacy: "Create or update the caller's pharmacy profile"), so
// this same form and the same call serve both first-time setup (redirected
// here on a 409, empty form) and later edits (prefilled from GET /me).

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Store, MapPin, Phone, Landmark } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import api from '../../../lib/api';
import type { PharmacyProfile } from '../../../types';

export default function PharmacyProfilePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [isJanAushadhi, setIsJanAushadhi] = useState(false);
  const [isNewPharmacy, setIsNewPharmacy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<PharmacyProfile>('/pharmacy/me');
      setName(res.data.name);
      setAddress(res.data.address || '');
      setPhone(res.data.phone || '');
      setIsJanAushadhi(res.data.is_jan_aushadhi);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setIsNewPharmacy(true);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'PHARMACIST') { router.push('/'); return; }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [user, authLoading, router, load]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Pharmacy name is required.');
      return;
    }
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      await api.post('/pharmacy/register', {
        name: name.trim(),
        address: address.trim() || undefined,
        phone: phone.trim() || undefined,
        is_jan_aushadhi: isJanAushadhi,
      });
      if (isNewPharmacy) {
        router.push('/pharmacy/dashboard');
        return;
      }
      setSaved(true);
    } catch {
      setError('Could not save. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading…</div>;
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <form onSubmit={submit} className="glass-panel p-8 max-w-lg w-full">
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500 flex items-center justify-center mb-4">
            <Store className="text-white" size={32} />
          </div>
          <h1 className="text-2xl font-bold">{isNewPharmacy ? 'Set up your pharmacy' : 'Pharmacy Profile'}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {isNewPharmacy
              ? "One-time setup — this is what patients and doctors will see. You can update it any time."
              : 'Update the details patients and doctors see when they search for you.'}
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-semibold mb-1 block">Pharmacy name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20"
              placeholder="e.g. Sri Ram Medicals"
            />
          </div>
          <div>
            <label className="text-sm font-semibold mb-1 flex items-center gap-1.5"><MapPin size={14} /> Address</label>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20"
              placeholder="Street, village/town, district"
            />
          </div>
          <div>
            <label className="text-sm font-semibold mb-1 flex items-center gap-1.5"><Phone size={14} /> Phone</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20"
              placeholder="Contact number"
            />
          </div>
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" checked={isJanAushadhi} onChange={(e) => setIsJanAushadhi(e.target.checked)} />
            <Landmark size={14} /> Jan Aushadhi store
          </label>
        </div>

        {error && <p role="alert" className="text-red-500 text-sm font-semibold mt-4">{error}</p>}
        {saved && <p className="text-emerald-600 text-sm font-semibold mt-4">Saved.</p>}

        <button disabled={saving} className="w-full mt-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl disabled:opacity-50">
          {saving ? 'Saving…' : isNewPharmacy ? 'Create Pharmacy' : 'Save Changes'}
        </button>
      </form>
    </div>
  );
}
