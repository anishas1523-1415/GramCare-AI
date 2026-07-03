"use client";

// Consultation booking — full flow per the planning doc:
// choose a doctor (specialty/experience/fee visible) -> pick a published
// slot -> pay the fee -> booking is created server-side against the
// verified payment order. The old page hardcoded DOCTOR_ID = 2 and booked
// any free-typed datetime with no payment check.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Stethoscope, CalendarDays, CheckCircle, ArrowLeft } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useProfile } from '../../contexts/ProfileContext';
import RazorpayCheckout from '../../components/RazorpayCheckout';
import api from '../../lib/api';
import type { DoctorPublic, Slot } from '../../types';

type Step = 'doctor' | 'slot' | 'pay' | 'done';

export default function AppointmentBooking() {
  const { user } = useAuth();
  const { activeProfile } = useProfile();

  const [step, setStep] = useState<Step>('doctor');
  const [doctors, setDoctors] = useState<DoctorPublic[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [doctor, setDoctor] = useState<DoctorPublic | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [symptoms, setSymptoms] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) return;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get<DoctorPublic[]>('/doctors');
        setDoctors(res.data.filter((d) => d.is_available));
      } catch {
        setError('Could not load the doctor directory.');
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const chooseDoctor = async (d: DoctorPublic) => {
    setDoctor(d);
    setError('');
    setLoading(true);
    try {
      const res = await api.get<Slot[]>(`/doctors/${d.id}/slots`);
      setSlots(res.data);
      setStep('slot');
    } catch {
      setError('Could not load available times for this doctor.');
    } finally {
      setLoading(false);
    }
  };

  const bookWithPayment = async (orderId: string | null) => {
    if (!doctor || !slot) return;
    try {
      await api.post('/appointments/book', {
        doctor_id: doctor.id,
        slot_id: slot.id,
        triage_summary: symptoms || null,
        family_profile_id: activeProfile?.id ?? null,
        payment_order_id: orderId,
      });
      setStep('done');
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string'
        ? message
        : 'Payment succeeded but booking failed. Your payment is refundable — please contact support.');
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to book an appointment.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-16 flex items-start justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-3xl w-full p-8 relative overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-teal-400/5 z-0"></div>
        <div className="relative z-10">
          <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
            <Stethoscope className="text-teal-500" /> Book a Consultation
          </h1>
          <p className="text-gray-500 mb-8">
            {activeProfile ? `Booking for ${activeProfile.full_name} (${activeProfile.relation})` : 'Booking for yourself'}
          </p>

          {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

          {/* STEP 1 — choose doctor */}
          {step === 'doctor' && (
            loading ? (
              <div className="flex justify-center p-10"><div className="animate-spin w-10 h-10 border-4 border-teal-500 border-t-transparent rounded-full" /></div>
            ) : doctors.length === 0 ? (
              <p className="text-gray-500 p-6 text-center">No doctors are currently available.</p>
            ) : (
              <div className="space-y-4">
                {doctors.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => chooseDoctor(d)}
                    className="w-full text-left p-5 rounded-2xl bg-white/50 dark:bg-black/30 border border-white/20 hover:ring-2 hover:ring-teal-400 transition-all"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="font-bold text-lg">{d.full_name}</div>
                        <div className="text-sm text-teal-600 font-semibold">{d.specialty}</div>
                        <div className="text-xs text-gray-500 mt-1">
                          {d.qualifications ? `${d.qualifications} · ` : ''}
                          {d.experience_years} yrs experience
                          {d.languages ? ` · Speaks ${d.languages.split(',').join(', ')}` : ''}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-extrabold text-indigo-500">₹{d.consultation_fee.toFixed(0)}</div>
                        <div className="text-xs text-gray-500">per consult</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )
          )}

          {/* STEP 2 — pick slot + describe symptoms */}
          {step === 'slot' && doctor && (
            <div>
              <button onClick={() => { setStep('doctor'); setSlot(null); }} className="flex items-center gap-1 text-sm text-gray-500 mb-4 hover:text-teal-500">
                <ArrowLeft size={16} /> Choose a different doctor
              </button>
              <h2 className="font-bold text-lg mb-3 flex items-center gap-2">
                <CalendarDays size={20} className="text-indigo-500" />
                Available times for {doctor.full_name}
              </h2>
              {slots.length === 0 ? (
                <p className="text-gray-500 p-4">This doctor has no open slots right now. Please check back later.</p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
                  {slots.map((s) => {
                    const dt = new Date(s.start_time);
                    return (
                      <button
                        key={s.id}
                        onClick={() => setSlot(s)}
                        className={`p-3 rounded-xl text-sm font-semibold border transition-all ${slot?.id === s.id ? 'bg-teal-500 text-white border-teal-500' : 'bg-white/50 dark:bg-black/30 border-white/20 hover:border-teal-400'}`}
                      >
                        {dt.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })}
                        <br />
                        {dt.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                      </button>
                    );
                  })}
                </div>
              )}

              <label className="block text-sm font-semibold mb-2">Describe the problem (shared with the doctor)</label>
              <textarea
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
                rows={3}
                className="w-full p-4 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:ring-2 focus:ring-teal-400 outline-none mb-6"
                placeholder="e.g. Fever and cough for 3 days…"
              />

              <button
                disabled={!slot}
                onClick={() => setStep('pay')}
                className="neu-button w-full py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-40"
              >
                Continue to payment — ₹{doctor.consultation_fee.toFixed(0)}
              </button>
            </div>
          )}

          {/* STEP 3 — pay (fee paid BEFORE the call, enforced server-side) */}
          {step === 'pay' && doctor && slot && (
            <div>
              <button onClick={() => setStep('slot')} className="flex items-center gap-1 text-sm text-gray-500 mb-4 hover:text-teal-500">
                <ArrowLeft size={16} /> Back
              </button>
              <div className="p-5 rounded-2xl bg-white/50 dark:bg-black/30 mb-6 text-sm space-y-1">
                <div><span className="font-bold">Doctor:</span> {doctor.full_name} ({doctor.specialty})</div>
                <div><span className="font-bold">Time:</span> {new Date(slot.start_time).toLocaleString()}</div>
                <div><span className="font-bold">Patient:</span> {activeProfile?.full_name || user.full_name || user.username}</div>
                <div><span className="font-bold">Fee:</span> ₹{doctor.consultation_fee.toFixed(0)} (refunded automatically if the doctor can&apos;t attend)</div>
              </div>
              {doctor.consultation_fee > 0 ? (
                <RazorpayCheckout
                  amount={doctor.consultation_fee}
                  onSuccess={(orderId) => bookWithPayment(orderId)}
                  onError={(msg) => setError(msg)}
                />
              ) : (
                <button
                  onClick={() => bookWithPayment(null)}
                  className="neu-button w-full py-3 bg-teal-500 text-white font-bold rounded-xl"
                >
                  Confirm free consultation
                </button>
              )}
            </div>
          )}

          {/* STEP 4 — done */}
          {step === 'done' && doctor && slot && (
            <div className="text-center py-10">
              <CheckCircle size={64} className="text-green-500 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-2">Appointment confirmed!</h2>
              <p className="text-gray-500">
                {doctor.full_name} · {new Date(slot.start_time).toLocaleString()}
              </p>
              <p className="text-sm text-gray-400 mt-4">
                You&apos;ll join the video consultation from your dashboard when it&apos;s time.
              </p>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
