"use client";

// The public, no-login side of the Digital Health Passport — what an EMT
// or hospital desk sees after scanning a patient's QR code. Deliberately
// works with zero authentication: someone in an emergency has no way to
// hand over a password, and the person reading this likely has no
// GramCare account of their own. See modules/passport/router.py for why
// this is safe (high-entropy capability token, minimal response shape).

import React, { useEffect, useState } from 'react';
import { use } from 'react';
import { Droplet, TriangleAlert, HeartPulse, Phone, Pill, ShieldAlert } from 'lucide-react';
import api from '../../../../lib/api';

interface PassportMedicine {
  name: string;
  dosage?: string | null;
  frequency?: string | null;
}

interface PassportContact {
  name: string;
  phone: string;
  relation?: string | null;
}

interface PassportPublic {
  full_name: string;
  blood_group?: string | null;
  allergies?: string | null;
  chronic_conditions?: string | null;
  emergency_contacts: PassportContact[];
  recent_medicines: PassportMedicine[];
}

export default function PublicPassportView({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [passport, setPassport] = useState<PassportPublic | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get<PassportPublic>(`/passport/${token}`);
        setPassport(res.data);
      } catch {
        setError('This health passport link is invalid or no longer active.');
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading…</div>;
  }

  if (error || !passport) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="glass-panel max-w-md w-full p-8 text-center">
          <ShieldAlert size={40} className="text-red-500 mx-auto mb-4" />
          <p className="text-gray-500">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 flex items-center justify-center">
      <div className="glass-panel max-w-lg w-full p-6 border-2 border-red-500/30">
        <div className="text-center mb-6">
          <p className="text-xs font-bold uppercase tracking-wider text-red-500">GramCare AI · Emergency Health Passport</p>
          <h1 className="text-2xl font-extrabold mt-1">{passport.full_name}</h1>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="glass-panel p-4 bg-red-500/10 border border-red-500/30 text-center">
            <Droplet size={22} className="text-red-500 mx-auto mb-1" />
            <p className="text-xs text-gray-500 font-semibold">Blood Group</p>
            <p className="text-xl font-extrabold">{passport.blood_group || '—'}</p>
          </div>
          <div className="glass-panel p-4 bg-amber-500/10 border border-amber-500/30 text-center">
            <TriangleAlert size={22} className="text-amber-500 mx-auto mb-1" />
            <p className="text-xs text-gray-500 font-semibold">Allergies</p>
            <p className="text-sm font-bold">{passport.allergies || 'None known'}</p>
          </div>
        </div>

        <div className="glass-panel p-4 mb-4">
          <p className="text-sm font-bold flex items-center gap-2 mb-2">
            <HeartPulse size={16} className="text-indigo-500" /> Chronic Conditions
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-300">
            {passport.chronic_conditions || 'None recorded'}
          </p>
        </div>

        {passport.recent_medicines.length > 0 && (
          <div className="glass-panel p-4 mb-4">
            <p className="text-sm font-bold flex items-center gap-2 mb-2">
              <Pill size={16} className="text-teal-500" /> Recently Prescribed Medicines
            </p>
            <ul className="text-sm text-gray-600 dark:text-gray-300 space-y-1">
              {passport.recent_medicines.map((m, i) => (
                <li key={i}>
                  {m.name}{m.dosage ? ` — ${m.dosage}` : ''}{m.frequency ? ` (${m.frequency})` : ''}
                </li>
              ))}
            </ul>
          </div>
        )}

        {passport.emergency_contacts.length > 0 && (
          <div className="glass-panel p-4">
            <p className="text-sm font-bold flex items-center gap-2 mb-2">
              <Phone size={16} className="text-emerald-500" /> Emergency Contacts
            </p>
            <ul className="text-sm space-y-2">
              {passport.emergency_contacts.map((c, i) => (
                <li key={i} className="flex justify-between">
                  <span>{c.name} {c.relation ? `(${c.relation})` : ''}</span>
                  <a href={`tel:${c.phone}`} className="text-indigo-500 font-semibold">{c.phone}</a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
