"use client";

// Laboratory booking queue — the portal's main screen. Planning doc: lab
// staff move a booking through BOOKED -> SAMPLE_COLLECTED -> PROCESSING ->
// REPORT_READY (report entry lives on its own screen, /report/[id]).

import React, { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import {
  FlaskConical, MapPin, Home, Clock, RefreshCw, XCircle, ArrowRight, ClipboardList,
} from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import type { LabBooking, BookingStatus } from '../../types';

const STATUS_STYLE: Record<BookingStatus, { label: string; className: string }> = {
  BOOKED: { label: 'Booked', className: 'bg-sky-500/15 text-sky-600 border-sky-500/30' },
  SAMPLE_COLLECTED: { label: 'Sample Collected', className: 'bg-amber-500/15 text-amber-600 border-amber-500/30' },
  PROCESSING: { label: 'Processing', className: 'bg-[var(--primary)]/15 text-[var(--primary)] border-[var(--primary)]/30 animate-pulse' },
  REPORT_READY: { label: 'Report Ready', className: 'bg-emerald-500/15 text-emerald-600 border-emerald-500/30' },
  COMPLETED: { label: 'Completed', className: 'bg-gray-400/15 text-gray-500 border-gray-400/30' },
  CANCELLED: { label: 'Cancelled', className: 'bg-red-500/10 text-red-500 border-red-500/30' },
};

const NEXT_ACTION: Partial<Record<BookingStatus, { label: string; next: BookingStatus }>> = {
  BOOKED: { label: 'Mark Sample Collected', next: 'SAMPLE_COLLECTED' },
  SAMPLE_COLLECTED: { label: 'Start Processing', next: 'PROCESSING' },
};

export default function LabDashboard() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [bookings, setBookings] = useState<LabBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actingOn, setActingOn] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchQueue = useCallback(async () => {
    try {
      const res = await api.get<LabBooking[]>('/lab/bookings/queue');
      setBookings(res.data);
      setLastUpdated(new Date());
      setError('');
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        router.replace('/onboarding');
        return;
      }
      setError('Could not load the booking queue.');
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    if (user.role !== 'LAB') {
      router.replace('/login');
      return;
    }
    fetchQueue();
    const poll = setInterval(fetchQueue, 30_000);
    return () => clearInterval(poll);
  }, [user, authLoading, router, fetchQueue]);

  const advance = async (booking: LabBooking, next: BookingStatus) => {
    setActingOn(booking.id);
    try {
      await api.put(`/lab/bookings/${booking.id}/status`, null, { params: { status: next } });
      await fetchQueue();
    } catch {
      setError(`Could not update booking #${booking.id}.`);
    } finally {
      setActingOn(null);
    }
  };

  const cancel = async (booking: LabBooking) => {
    if (!confirm(`Cancel the ${booking.test_name} booking for patient #${booking.patient_id}?`)) return;
    await advance(booking, 'CANCELLED');
  };

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading booking queue…</div>;
  }

  return (
    <div className="max-w-6xl mx-auto p-6 lg:p-10">
      <header className="flex flex-wrap justify-between items-center gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-extrabold flex items-center gap-3">
            <FlaskConical className="text-[var(--primary)]" size={34} /> Booking Queue
          </h1>
          {lastUpdated && (
            <p className="text-sm text-gray-500 mt-1">Updated {lastUpdated.toLocaleTimeString()}</p>
          )}
        </div>
        <button onClick={fetchQueue} className="neu-button px-4 py-2 font-bold rounded-xl flex items-center gap-2 text-sm">
          <RefreshCw size={15} /> Refresh
        </button>
      </header>

      {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

      {bookings.length === 0 ? (
        <div className="glass-panel p-12 text-center text-gray-500">
          <ClipboardList size={40} className="mx-auto mb-3 opacity-50" />
          No bookings need action right now.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          <AnimatePresence>
            {bookings.map((b) => {
              const style = STATUS_STYLE[b.status];
              const action = NEXT_ACTION[b.status];
              return (
                <motion.div
                  key={b.id}
                  layout
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.96 }}
                  className="glass-panel p-5"
                >
                  <div className="flex justify-between items-start mb-3">
                    <span className={`text-xs font-bold px-3 py-1 rounded-full border ${style.className}`}>
                      {style.label}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-gray-500">
                      <Clock size={12} /> {new Date(b.created_at).toLocaleString()}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold mb-1">{b.test_name}</h3>
                  <p className="text-sm text-gray-500 mb-1">Patient #{b.patient_id}</p>

                  <p className="text-sm flex items-center gap-1 mb-1 text-gray-600 dark:text-gray-300">
                    {b.home_collection ? <Home size={14} /> : <MapPin size={14} />}
                    {b.home_collection ? 'Home sample collection' : 'In-center visit'}
                  </p>
                  {b.notes && <p className="text-sm italic text-gray-500 mb-2">&ldquo;{b.notes}&rdquo;</p>}

                  <div className="flex gap-2 mt-4">
                    {b.status === 'PROCESSING' ? (
                      <button
                        onClick={() => router.push(
                          `/report/${b.id}?test=${encodeURIComponent(b.test_name)}&patient=${b.patient_id}`
                        )}
                        className="flex-1 py-2.5 bg-[var(--primary)] hover:opacity-90 text-white font-bold rounded-xl transition-opacity flex items-center justify-center gap-2 text-sm"
                      >
                        Enter Report <ArrowRight size={16} />
                      </button>
                    ) : action ? (
                      <button
                        disabled={actingOn === b.id}
                        onClick={() => advance(b, action.next)}
                        className="flex-1 py-2.5 bg-[var(--primary)] hover:opacity-90 text-white font-bold rounded-xl transition-opacity disabled:opacity-50 text-sm"
                      >
                        {actingOn === b.id ? 'Updating…' : action.label}
                      </button>
                    ) : null}
                    {(b.status === 'BOOKED' || b.status === 'SAMPLE_COLLECTED') && (
                      <button
                        disabled={actingOn === b.id}
                        onClick={() => cancel(b)}
                        className="px-3 py-2.5 border border-red-500/40 text-red-500 rounded-xl hover:bg-red-500/10 transition-colors"
                        title="Cancel booking"
                        aria-label={`Cancel ${b.test_name} booking for patient #${b.patient_id}`}
                      >
                        <XCircle size={18} />
                      </button>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
