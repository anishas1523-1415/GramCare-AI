"use client";

// Patient-facing appointments list. This was the actual root cause behind
// "doctor can't attend/view the consultation call": the booking flow
// (book/page.tsx's confirmation step) told patients "You'll join the video
// consultation from your dashboard when it's time" — but no such dashboard,
// list, or join link existed anywhere in web_portal. The doctor's queue
// always had a working "Consult" button pointing at /consultation/{id};
// patients had nothing pointing at the same room, so a doctor joining that
// room was always alone. This page is that missing other half.

import { motion } from "framer-motion";
import { CalendarClock, Video, XCircle, User } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useRouter } from "next/navigation";
import api from "../../lib/api";
import type { Appointment, DoctorPublic } from "../../types";

const STATUS_STYLE: Record<Appointment["status"], string> = {
  PENDING: "bg-amber-500/15 text-amber-500 border-amber-500/30",
  CONFIRMED: "bg-indigo-500/15 text-indigo-500 border-indigo-500/30",
  COMPLETED: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
  CANCELLED: "bg-red-500/15 text-red-500 border-red-500/30",
};

export default function MyAppointmentsPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [doctors, setDoctors] = useState<Record<number, DoctorPublic>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [apptRes, doctorsRes] = await Promise.all([
        api.get<Appointment[]>("/appointments/my"),
        api.get<DoctorPublic[]>("/doctors"),
      ]);
      setAppointments(apptRes.data.sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime()));
      setDoctors(Object.fromEntries(doctorsRes.data.map((d) => [d.id, d])));
    } catch {
      setError("Could not load your appointments.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const cancelAppointment = async (id: number) => {
    setCancellingId(id);
    try {
      await api.put(`/appointments/${id}`, { status: "CANCELLED" });
      await load();
    } catch {
      setError("Could not cancel this appointment.");
    } finally {
      setCancellingId(null);
    }
  };

  const upcoming = useMemo(
    () => appointments.filter((a) => a.status === "PENDING" || a.status === "CONFIRMED"),
    [appointments]
  );
  const past = useMemo(
    () => appointments.filter((a) => a.status === "COMPLETED" || a.status === "CANCELLED"),
    [appointments]
  );

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to view your appointments.</p>
      </div>
    );
  }

  const renderCard = (appt: Appointment) => {
    const doctor = doctors[appt.doctor_id];
    return (
      <div key={appt.id} className="neu-panel p-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <User size={16} className="text-indigo-500" />
              <p className="font-bold">{doctor ? doctor.full_name : `Doctor #${appt.doctor_id}`}</p>
              <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${STATUS_STYLE[appt.status]}`}>
                {appt.status}
              </span>
            </div>
            {doctor?.specialty && <p className="text-xs text-gray-400 mb-1">{doctor.specialty}</p>}
            <p className="text-sm text-gray-500 flex items-center gap-1.5">
              <CalendarClock size={14} /> {new Date(appt.scheduled_at).toLocaleString()}
            </p>
            {appt.triage_summary && (
              <p className="text-xs text-gray-400 mt-1">Reason: {appt.triage_summary}</p>
            )}
          </div>

          {(appt.status === "PENDING" || appt.status === "CONFIRMED") && (
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={() => router.push(`/consultation/${appt.id}`)}
                className="neu-button px-4 py-2 bg-indigo-500 text-white rounded-lg flex items-center justify-center gap-2 text-sm font-semibold"
              >
                <Video size={16} /> Join Consultation
              </button>
              <button
                type="button"
                onClick={() => cancelAppointment(appt.id)}
                disabled={cancellingId === appt.id}
                title="Cancel appointment"
                className="p-2 border border-red-500/40 text-red-500 rounded-lg hover:bg-red-500/10 transition-colors disabled:opacity-50"
              >
                <XCircle size={18} />
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen p-6 lg:p-16 flex items-start justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-2xl w-full p-8"
      >
        <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
          <CalendarClock className="text-indigo-500" /> My Appointments
        </h1>
        <p className="text-gray-500 mb-8">Join a video consultation, or manage an upcoming booking.</p>

        {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

        {loading ? (
          <p className="text-center text-gray-400 py-12">Loading…</p>
        ) : (
          <>
            <div className="space-y-3 mb-8">
              {upcoming.length === 0 ? (
                <p className="text-gray-400 text-sm">No upcoming appointments. <a href="/book" className="text-indigo-500 font-semibold hover:underline">Book a consultation</a>.</p>
              ) : (
                upcoming.map(renderCard)
              )}
            </div>

            {past.length > 0 && (
              <div>
                <h2 className="text-lg font-bold mb-3">Past Appointments</h2>
                <div className="space-y-3">{past.map(renderCard)}</div>
              </div>
            )}
          </>
        )}
      </motion.div>
    </div>
  );
}
