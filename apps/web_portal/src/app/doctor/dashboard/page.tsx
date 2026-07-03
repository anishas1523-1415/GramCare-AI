"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Users, Calendar, ShieldAlert, Video, FileText, CheckCircle, Clock, Plus, Trash2 } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import api from '../../../lib/api';
import { io } from 'socket.io-client';
import type { Slot } from '../../../types';

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

  useEffect(() => { load(); }, [load]);

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

export default function DoctorDashboard() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  
  const [appointments, setAppointments] = useState<any[]>([]);
  const [activeSOS, setActiveSOS] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [socketConnected, setSocketConnected] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    
    // Redirect non-doctors
    if (!user || user.role !== "DOCTOR") {
      router.push("/");
      return;
    }

    const fetchData = async () => {
      try {
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
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:4000";
    const socket = io(WS_URL, {
      auth: { token: localStorage.getItem('access_token') },
    });

    socket.on("connect", () => {
      setSocketConnected(true);
      socket.emit("join_department", "General Medicine");
    });

    socket.on("disconnect", () => setSocketConnected(false));
    
    socket.on("emergency_alert", (data) => {
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
    } catch (error) {
      alert("Failed to respond to SOS.");
    }
  };

  const completeAppointment = async (apptId: number) => {
    try {
      await api.put(`/appointments/${apptId}`, { status: "COMPLETED" });
      setAppointments(appointments.filter(app => app.id !== apptId));
    } catch (error) {
      alert("Failed to complete appointment.");
    }
  };

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading Doctor Portal...</div>;
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
          <button className="neu-button px-6 py-2 bg-indigo-500 text-white font-bold rounded-xl flex items-center gap-2">
            <Video size={20} /> Tele-ICU
          </button>
        </div>
      </header>

      {/* Active Emergencies (High Priority) */}
      {activeSOS.length > 0 && (
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-12">
          <h2 className="text-2xl font-bold text-red-500 mb-6 flex items-center gap-2">
            <ShieldAlert className="animate-pulse" /> Active Emergencies
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {activeSOS.map(sos => (
              <div key={sos.id} className="bg-red-500/10 border border-red-500/30 p-6 rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4">
                  <span className="bg-red-500 text-white text-xs font-bold px-3 py-1 rounded-full animate-pulse">CRITICAL</span>
                </div>
                <h3 className="text-xl font-bold mb-2">SOS from Patient #{sos.patient_id}</h3>
                <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">Location: {sos.location_text || `${sos.location_lat}, ${sos.location_lng}`}</p>
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
                      </div>
                      <p className="text-sm text-gray-500">Scheduled: {new Date(appt.scheduled_at).toLocaleString()}</p>
                      {appt.triage_summary && <p className="text-sm mt-2 text-gray-600 dark:text-gray-300"><strong>Triage:</strong> {appt.triage_summary}</p>}
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
