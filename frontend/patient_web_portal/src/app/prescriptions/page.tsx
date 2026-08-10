"use client";

// Patient-facing prescriptions view. Closes the loop the audit flagged:
// doctors could write prescriptions but patients had no page to see them.
// Scoped to the active family member when one is selected.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, CheckCircle, Clock } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useProfile } from '../../contexts/ProfileContext';
import ThemedLoader from '../../components/ThemedLoader';
import type { Prescription } from '../../types';

export default function MyPrescriptions() {
  const { user } = useAuth();
  const { activeProfile } = useProfile();
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const res = await api.get<Prescription[]>('/ehr/prescriptions/my', {
          params: activeProfile ? { family_profile_id: activeProfile.id } : {},
        });
        if (!cancelled) setPrescriptions(res.data);
      } catch {
        if (!cancelled) setError('Could not load prescriptions. Please try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, activeProfile]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to view prescriptions.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-24">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-4xl font-extrabold flex items-center gap-3 mb-2">
          <FileText className="text-indigo-500" size={40} />
          {activeProfile ? `${activeProfile.full_name}'s Prescriptions` : 'My Prescriptions'}
        </h1>
        <p className="text-gray-500 mb-10">
          Digital prescriptions from your consultations — automatically shared with the pharmacy network.
        </p>

        {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

        {loading ? (
          <ThemedLoader variant="wallet" label="Loading your prescriptions…" />
        ) : prescriptions.length === 0 ? (
          <div className="glass-panel p-10 text-center text-gray-500">
            No prescriptions yet. They will appear here after a doctor consultation.
          </div>
        ) : (
          <div className="space-y-6">
            {prescriptions.map((rx) => (
              <motion.div
                key={rx.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-panel p-6"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-xl font-bold">{rx.diagnosis || `Prescription #${rx.id}`}</h3>
                    <p className="text-sm text-gray-500">
                      {new Date(rx.created_at).toLocaleString()}
                    </p>
                  </div>
                  <span className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold ${rx.is_fulfilled ? 'bg-green-500/10 text-green-600' : 'bg-orange-500/10 text-orange-600'}`}>
                    {rx.is_fulfilled ? <><CheckCircle size={14} /> Collected</> : <><Clock size={14} /> Awaiting pickup</>}
                  </span>
                </div>

                <div className="space-y-2">
                  {rx.medicines.map((m, i) => (
                    <div key={i} className="flex justify-between p-3 rounded-xl bg-white/40 dark:bg-black/30 text-sm">
                      <span className="font-semibold">{m.name}</span>
                      <span className="text-gray-500">{m.dosage} · {m.frequency} · {m.duration}</span>
                    </div>
                  ))}
                </div>

                {rx.dosage_instructions && (
                  <p className="mt-4 text-sm"><span className="font-bold">Instructions: </span>{rx.dosage_instructions}</p>
                )}
                {rx.notes && (
                  <p className="mt-1 text-sm text-gray-500"><span className="font-bold">Notes: </span>{rx.notes}</p>
                )}
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
