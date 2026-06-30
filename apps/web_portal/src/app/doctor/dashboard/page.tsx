"use client";

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, Calendar, ShieldAlert, Video, FileText, CheckCircle } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import api from '../../../lib/api';
import { io } from 'socket.io-client';

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
        // Fetch queue and SOS from actual backend
        // Temporarily hardcoding doctor ID to 2 for demo purposes if it's not in the token
        const doctorId = 2; 
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

    // Setup real-time listeners for new SOS or triage alerts
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:4000";
    const socket = io(WS_URL);

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
                        onClick={() => router.push(`/doctor/prescription/${appt.id}`)}
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
          <div className="neu-panel p-6">
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2"><Users className="text-indigo-500" /> Patient Directory</h2>
            <div className="text-center p-6 bg-[var(--background)] shadow-[var(--shadow-neu-flat)] rounded-xl">
              <div className="text-3xl font-extrabold text-indigo-500 mb-2">1,245</div>
              <p className="text-gray-500 text-sm">Total Registered Patients</p>
            </div>
            <button className="w-full mt-4 py-3 bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-bold rounded-xl">
              View Directory
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
