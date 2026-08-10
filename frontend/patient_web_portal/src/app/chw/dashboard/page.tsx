"use client";

// Rural Community Health Worker (CHW) tooling (modules/chw/router.py): a
// field health worker registers a walk-in villager who may have no phone,
// email, or literacy to self-register, then acts on that patient's behalf
// for triage and booking. See the backend module docstring for the full
// design contract — in particular, a paid doctor still requires the
// patient's OWN verified payment; there is no "CHW collects cash" concept,
// so the booking widget below only offers free-consultation doctors.

import { useCallback, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users, UserPlus, Stethoscope, CalendarDays, ChevronDown, ChevronRight,
  Copy, Check, AlertTriangle,
} from "lucide-react";
import { useAuth } from "../../../contexts/AuthContext";
import ThemedLoader from "../../../components/ThemedLoader";
import api from "../../../lib/api";
import type {
  CHWPatientSummary, CHWPatientRegisterResponse, TriageResult, DoctorPublic, Slot,
} from "../../../types";

function RegisterPatientForm({ onRegistered }: { onRegistered: () => void }) {
  const [fullName, setFullName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("Female");
  const [phone, setPhone] = useState("");
  const [addressNote, setAddressNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CHWPatientRegisterResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !age) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await api.post<CHWPatientRegisterResponse>("/chw/register-patient", {
        full_name: fullName,
        age: Number(age),
        gender,
        phone: phone || undefined,
        address_note: addressNote || undefined,
      });
      setResult(res.data);
      setFullName("");
      setAge("");
      setPhone("");
      setAddressNote("");
      onRegistered();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === "string" ? message : "Could not register this patient.");
    } finally {
      setSubmitting(false);
    }
  };

  const copyCredentials = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(`Username: ${result.username}\nPassword: ${result.temporary_password}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can fail silently (permissions/non-secure context) — the
      // credentials are still visible on screen, so this is not fatal.
    }
  };

  return (
    <div className="neu-panel p-6">
      <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
        <UserPlus className="text-teal-500" /> Register a Walk-in Patient
      </h2>

      {result && (
        <div className="mb-5 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-sm">
          <p className="font-bold text-emerald-600 mb-2">Patient registered — write these down now</p>
          <div className="flex items-center justify-between gap-3 font-mono text-sm bg-white/50 dark:bg-black/30 rounded-lg p-3">
            <div>
              <div>Username: <span className="font-bold">{result.username}</span></div>
              <div>Password: <span className="font-bold">{result.temporary_password}</span></div>
            </div>
            <button
              type="button"
              onClick={copyCredentials}
              className="neu-button p-2 rounded-lg shrink-0"
              title="Copy credentials"
            >
              {copied ? <Check size={16} className="text-emerald-500" /> : <Copy size={16} />}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2">{result.message}</p>
        </div>
      )}

      {error && <p role="alert" className="text-red-500 text-sm font-semibold mb-4">{error}</p>}

      <form onSubmit={submit} className="grid sm:grid-cols-2 gap-3">
        <div className="sm:col-span-2">
          <label htmlFor="chw-full-name" className="block text-xs font-semibold mb-1">Full name</label>
          <input
            id="chw-full-name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            className="w-full p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
            placeholder="e.g. Muthu Selvam"
          />
        </div>
        <div>
          <label htmlFor="chw-age" className="block text-xs font-semibold mb-1">Age</label>
          <input
            id="chw-age"
            type="number"
            min={0}
            max={150}
            value={age}
            onChange={(e) => setAge(e.target.value)}
            required
            className="w-full p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
          />
        </div>
        <div>
          <label htmlFor="chw-gender" className="block text-xs font-semibold mb-1">Gender</label>
          <select
            id="chw-gender"
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="w-full p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
          >
            <option>Female</option>
            <option>Male</option>
            <option>Other</option>
          </select>
        </div>
        <div>
          <label htmlFor="chw-phone" className="block text-xs font-semibold mb-1">Phone (optional)</label>
          <input
            id="chw-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
            placeholder="9XXXXXXXXX"
          />
        </div>
        <div>
          <label htmlFor="chw-address" className="block text-xs font-semibold mb-1">Address note (optional)</label>
          <input
            id="chw-address"
            value={addressNote}
            onChange={(e) => setAddressNote(e.target.value)}
            className="w-full p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
            placeholder="e.g. Near the village well"
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !fullName || !age}
          className="sm:col-span-2 neu-button py-2.5 bg-teal-500 text-white font-bold rounded-lg disabled:opacity-50"
        >
          {submitting ? "Registering…" : "Register Patient"}
        </button>
      </form>
    </div>
  );
}

function TriagePanel({ patient }: { patient: CHWPatientSummary }) {
  const [symptoms, setSymptoms] = useState("");
  const [age, setAge] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TriageResult | null>(null);

  const run = async () => {
    if (!symptoms || !age) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.post<TriageResult>(`/chw/patients/${patient.id}/triage`, {
        symptoms_text: symptoms,
        age: Number(age),
      });
      setResult(res.data);
    } catch {
      setError("Could not run triage for this patient.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 rounded-xl bg-white/40 dark:bg-black/20 border border-white/10">
      <label htmlFor={`chw-symptoms-${patient.id}`} className="block text-xs font-semibold mb-1">Symptoms</label>
      <textarea
        id={`chw-symptoms-${patient.id}`}
        value={symptoms}
        onChange={(e) => setSymptoms(e.target.value)}
        rows={2}
        className="w-full p-2.5 rounded-lg bg-white/50 dark:bg-black/30 border border-white/20 text-sm focus:ring-2 focus:ring-teal-400 outline-none mb-2"
        placeholder="e.g. Fever and body ache for two days"
      />
      <div className="flex gap-2 mb-3">
        <input
          type="number"
          min={0}
          max={150}
          value={age}
          onChange={(e) => setAge(e.target.value)}
          placeholder="Age"
          className="w-24 p-2 rounded-lg bg-white/50 dark:bg-black/30 border border-white/20 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
        />
        <button
          type="button"
          onClick={run}
          disabled={loading || !symptoms || !age}
          className="neu-button px-4 py-2 bg-indigo-500 text-white text-sm font-bold rounded-lg disabled:opacity-50"
        >
          {loading ? "Analyzing…" : "Run AI Triage"}
        </button>
      </div>

      {error && <p role="alert" className="text-red-500 text-xs font-semibold mb-2">{error}</p>}

      {result && (
        <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-sm space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-bold">{result.predicted_condition}</span>
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-600">
              Severity {result.severity_score}
            </span>
          </div>
          <p className="text-xs text-gray-600 dark:text-gray-300">{result.doctor_recommendation}</p>
          {result.home_remedies && (
            <p className="text-xs text-gray-500"><span className="font-semibold">Home care:</span> {result.home_remedies}</p>
          )}
          <p className="text-[11px] text-gray-400 pt-1 border-t border-white/10 mt-1">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}

function BookingPanel({ patient }: { patient: CHWPatientSummary }) {
  const [doctors, setDoctors] = useState<DoctorPublic[]>([]);
  const [doctor, setDoctor] = useState<DoctorPublic | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [booked, setBooked] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await api.get<DoctorPublic[]>("/doctors");
        setDoctors(res.data.filter((d) => d.is_available && d.consultation_fee === 0));
      } catch {
        setError("Could not load doctors.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const chooseDoctor = async (d: DoctorPublic) => {
    setDoctor(d);
    setError("");
    try {
      const res = await api.get<Slot[]>(`/doctors/${d.id}/slots`);
      setSlots(res.data);
    } catch {
      setError("Could not load this doctor's available times.");
    }
  };

  const book = async (slotId: number) => {
    if (!doctor) return;
    setError("");
    try {
      await api.post(`/chw/patients/${patient.id}/book`, {
        doctor_id: doctor.id,
        slot_id: slotId,
      });
      setBooked(true);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === "string" ? message : "Could not book this consultation.");
    }
  };

  if (booked) {
    return (
      <p className="text-sm text-emerald-600 font-semibold p-3">
        Consultation booked for {patient.full_name}.
      </p>
    );
  }

  return (
    <div className="p-4 rounded-xl bg-white/40 dark:bg-black/20 border border-white/10">
      <p className="text-xs text-gray-500 mb-3 flex items-start gap-1.5">
        <AlertTriangle size={13} className="shrink-0 mt-0.5" />
        Only free consultations can be booked here — a paid doctor requires the
        patient&apos;s own payment, so this list only shows doctors with no fee.
      </p>
      {error && <p role="alert" className="text-red-500 text-xs font-semibold mb-2">{error}</p>}
      {loading ? (
        <p className="text-sm text-gray-500">Loading doctors…</p>
      ) : !doctor ? (
        doctors.length === 0 ? (
          <p className="text-sm text-gray-500">No free-consultation doctors are available right now.</p>
        ) : (
          <div className="space-y-2">
            {doctors.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => chooseDoctor(d)}
                className="w-full text-left p-3 rounded-lg bg-white/50 dark:bg-black/30 border border-white/20 hover:ring-2 hover:ring-teal-400 transition-all text-sm"
              >
                <span className="font-bold">{d.full_name}</span>
                <span className="text-teal-600 font-semibold ml-2">{d.specialty}</span>
              </button>
            ))}
          </div>
        )
      ) : (
        <div>
          <button
            type="button"
            onClick={() => { setDoctor(null); setSlots([]); }}
            className="text-xs text-gray-500 mb-2 hover:text-teal-500"
          >
            &larr; Choose a different doctor
          </button>
          {slots.length === 0 ? (
            <p className="text-sm text-gray-500">This doctor has no open slots right now.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {slots.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => book(s.id)}
                  className="p-2 rounded-lg text-xs font-semibold border border-white/20 bg-white/50 dark:bg-black/30 hover:border-teal-400 transition-all"
                >
                  {new Date(s.start_time).toLocaleString(undefined, {
                    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                  })}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PatientRow({ patient }: { patient: CHWPatientSummary }) {
  const [expanded, setExpanded] = useState<"triage" | "book" | null>(null);

  return (
    <div className="p-4 rounded-xl bg-white/50 dark:bg-black/30 border border-white/20">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-bold">{patient.full_name}</p>
          <p className="text-xs text-gray-500">
            @{patient.username}{patient.phone ? ` · ${patient.phone}` : ""} · registered {new Date(patient.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setExpanded(expanded === "triage" ? null : "triage")}
            className={`neu-button px-3 py-1.5 text-xs font-bold rounded-lg flex items-center gap-1 ${expanded === "triage" ? "bg-indigo-500 text-white" : ""}`}
          >
            <Stethoscope size={13} /> Triage {expanded === "triage" ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </button>
          <button
            type="button"
            onClick={() => setExpanded(expanded === "book" ? null : "book")}
            className={`neu-button px-3 py-1.5 text-xs font-bold rounded-lg flex items-center gap-1 ${expanded === "book" ? "bg-teal-500 text-white" : ""}`}
          >
            <CalendarDays size={13} /> Book {expanded === "book" ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </button>
        </div>
      </div>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="pt-3 mt-3 border-t border-white/10">
              {expanded === "triage" ? <TriagePanel patient={patient} /> : <BookingPanel patient={patient} />}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function CHWDashboard() {
  const { user, loading: authLoading } = useAuth();
  const [patients, setPatients] = useState<CHWPatientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<CHWPatientSummary[]>("/chw/my-patients");
      setPatients(res.data);
    } catch {
      setError("Could not load your registered patients.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (user) void loadPatients();
  }, [user, loadPatients]);

  if (authLoading) {
    return <ThemedLoader variant="doctor" label="Loading…" />;
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to see your CHW dashboard.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 lg:p-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-4xl mx-auto space-y-8"
      >
        <div>
          <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
            <Users className="text-teal-500" /> CHW Dashboard
          </h1>
          <p className="text-gray-500">
            Register walk-in villagers and manage triage or booking on their behalf.
          </p>
        </div>

        <RegisterPatientForm onRegistered={loadPatients} />

        <div className="neu-panel p-6">
          <h2 className="text-xl font-bold mb-4">My Registered Patients</h2>
          {error && <p role="alert" className="text-red-500 text-sm font-semibold mb-4">{error}</p>}
          {loading ? (
            <p className="text-sm text-gray-500 text-center py-6">Loading…</p>
          ) : patients.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-6">
              You haven&apos;t registered any patients yet.
            </p>
          ) : (
            <div className="space-y-3">
              {patients.map((p) => (
                <PatientRow key={p.id} patient={p} />
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
