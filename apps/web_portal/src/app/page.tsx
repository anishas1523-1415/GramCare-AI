"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Activity, ShieldAlert, Radio, Brain, ChevronDown, Stethoscope, Camera, X } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { io } from "socket.io-client";
import api from "../lib/api";
import { useProfile } from "../contexts/ProfileContext";

interface TriageResult {
  severity: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  severity_score?: number;
  department: string;
  recommendation: string;
  home_remedies?: string;
  first_aid?: string;
  possible_causes?: string;
  specialist_type?: string;
  untreated_outcome?: string;
  confidence?: number;
  explanation?: string;
}

interface TriageAlert {
  id: string;
  time: string;
  severity: string;
  department: string;
  symptoms: string;
  isEmergency?: boolean;
}

// Module-level: this never changes across renders, so defining it inside
// the component (as it previously was, twice, under two different names)
// either duplicated the value or forced a choice between silencing
// exhaustive-deps and recreating the socket connection every render.
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "https://gramcare-signaling.onrender.com";

export default function Home() {
  const { activeProfile } = useProfile();
  const router = useRouter();
  const [symptoms, setSymptoms] = useState("");
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showExplanation, setShowExplanation] = useState(false);
  // Optional symptom photo (planning doc: text/voice plus an optional
  // image, e.g. a rash or visible wound, factored into the same AI
  // severity assessment — distinct from prescription OCR).
  const [symptomImage, setSymptomImage] = useState<{ preview: string; base64: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      setSymptomImage({ preview: result, base64: result.split(",")[1] });
    };
    reader.readAsDataURL(file);
  };
  
  // Realtime Socket State
  const [alerts, setAlerts] = useState<TriageAlert[]>([]);
  const [socketConnected, setSocketConnected] = useState(false);

  useEffect(() => {
    // Connect to Node.js Realtime Server
    const socket = io(WS_URL);

    socket.on("connect", () => {
      setSocketConnected(true);
      // NOTE: this page is reachable by guests (pre-login), so this socket
      // has no auth token. The signaling server now requires authentication
      // to join a department room, so this call is intentionally a no-op
      // for guests — they will still receive global CRITICAL emergency
      // broadcasts (unauthenticated-safe by design) but not department-
      // scoped triage_update alerts. That requires being logged in.
      socket.emit("join_department", "General Medicine");
    });

    socket.on("disconnect", () => {
      setSocketConnected(false);
    });

    // Listen for triage updates (simulated emergency alerts)
    socket.on("triage_update", (data: TriageAlert) => {
      setAlerts((prev) => [data, ...prev].slice(0, 5)); // Keep last 5
    });

    socket.on("emergency_alert", (data: TriageAlert) => {
      setAlerts((prev) => [{ ...data, isEmergency: true }, ...prev].slice(0, 5));
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const analyzeSymptoms = async () => {
    if (!symptoms.trim()) return;
    
    setLoading(true);
    setError("");
    setTriageResult(null);
    setShowExplanation(false);

    try {
      // Connect to the FastAPI Backend (unified API)
      const res = await api.post("/triage/analyze", {
        symptoms_text: symptoms,
        patient_id: "GUEST", // attribution happens server-side via the JWT when logged in
        age: activeProfile?.age ?? 30,
        family_profile_id: activeProfile?.id ?? null,
        image_base64: symptomImage?.base64 ?? null,
      });

      const data = res.data;
      
      // Map backend response to UI format
      const severityLabel = data.severity_score >= 75 ? "CRITICAL" 
        : data.severity_score >= 50 ? "HIGH" 
        : data.severity_score >= 25 ? "MODERATE" 
        : "LOW";
      
      setTriageResult({
        severity: severityLabel,
        severity_score: data.severity_score,
        department: data.predicted_condition,
        recommendation: data.doctor_recommendation,
        home_remedies: data.home_remedies,
        first_aid: data.first_aid,
        possible_causes: data.possible_causes,
        specialist_type: data.specialist_type,
        untreated_outcome: data.untreated_outcome,
        confidence: data.confidence_score,
        explanation: data.explanation,
      });
      
      // Emit triage alert to the WebSocket server for the Doctor Portal live feed
      const socket = io(WS_URL);
      socket.emit("new_triage_alert", {
        id: Math.random().toString(36).substring(7),
        time: new Date().toLocaleTimeString(),
        severity: severityLabel,
        department: data.predicted_condition,
        symptoms: symptoms.substring(0, 50) + (symptoms.length > 50 ? "..." : ""),
      });
      setTimeout(() => socket.disconnect(), 1000);

    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center p-8 lg:p-24 relative overflow-hidden">
      {/* Background blobs for Glassmorphism effect */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <motion.div
          animate={{ scale: [1, 1.2, 1], rotate: [0, 90, 0] }}
          transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
          className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40"
        />
        <motion.div
          animate={{ scale: [1, 1.3, 1], rotate: [0, -90, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: "linear" }}
          className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-teal-400 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40"
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="text-center mb-16"
      >
        <h1 className="text-5xl font-extrabold tracking-tight lg:text-7xl mb-4 text-[var(--foreground)]">
          GramCare <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-teal-400">AI</span>
        </h1>
        <p className="text-xl text-gray-500 dark:text-gray-400 max-w-2xl mx-auto flex items-center justify-center gap-2">
          The ultimate hybrid healthcare ecosystem.
          {socketConnected ? (
            <span className="flex items-center text-sm font-bold text-green-500 bg-green-500/10 px-3 py-1 rounded-full"><Radio size={16} className="mr-2 animate-pulse" /> Live</span>
          ) : (
            <span className="flex items-center text-sm font-bold text-red-500 bg-red-500/10 px-3 py-1 rounded-full"><Radio size={16} className="mr-2" /> Offline</span>
          )}
        </p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 w-full max-w-6xl">
        
        {/* Interactive Glassmorphism Card: AI Symptom Checker */}
        <motion.div
          className="glass-panel p-8 flex flex-col items-center justify-center text-center relative overflow-hidden min-h-[400px]"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 to-teal-400/10 z-0"></div>
          
          <div className="z-10 w-full">
            <div className="w-16 h-16 mx-auto rounded-xl bg-white/20 backdrop-blur-md border border-white/30 flex items-center justify-center mb-6 text-teal-400">
              <Activity size={32} />
            </div>
            <h2 className="text-2xl font-bold mb-4">AI Symptom Checker</h2>
            
            <textarea
              className="w-full p-4 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-teal-400 mb-4 resize-none"
              rows={3}
              placeholder="Describe your symptoms (e.g. fever, headache, cough)..."
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
            />

            {/* Optional symptom photo */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="hidden"
            />
            {symptomImage ? (
              <div className="relative mb-4 rounded-xl overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element -- user-selected local file preview, not a served asset */}
                <img src={symptomImage.preview} alt="Symptom photo" className="w-full h-32 object-cover" />
                <button
                  onClick={() => { setSymptomImage(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}
                  className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 text-white flex items-center justify-center"
                >
                  <X size={14} />
                </button>
              </div>
            ) : (
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full mb-4 py-2.5 rounded-xl border border-teal-400/50 text-teal-600 dark:text-teal-400 text-sm font-semibold flex items-center justify-center gap-2 hover:bg-teal-400/10 transition-colors"
              >
                <Camera size={16} /> Add a photo of the symptom (optional)
              </button>
            )}

            <button
              onClick={analyzeSymptoms}
              disabled={loading || !symptoms.trim()}
              className="neu-button w-full py-3 bg-teal-500 text-white flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
                    className="inline-flex"
                  >
                    <Brain size={18} />
                  </motion.span>
                  <span>AI is thinking…</span>
                </>
              ) : (
                "Analyze with AI"
              )}
            </button>

            {error && <p className="text-red-500 mt-4 text-sm font-semibold">{error}</p>}

            {triageResult && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 p-4 rounded-xl bg-white/40 dark:bg-black/40 border border-white/20 text-left"
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="font-bold">Severity:</span>
                  <span className={`px-2 py-1 rounded text-xs font-bold ${
                    triageResult.severity === 'CRITICAL' ? 'bg-red-500 text-white' :
                    triageResult.severity === 'HIGH' ? 'bg-orange-500 text-white' :
                    triageResult.severity === 'MODERATE' ? 'bg-yellow-500 text-black' :
                    'bg-green-500 text-white'
                  }`}>
                    {triageResult.severity}
                  </span>
                </div>
                <div className="mb-2">
                  <span className="font-bold">Department: </span> 
                  {triageResult.department}
                </div>
                <div className="mb-2">
                  <span className="font-bold">Recommendation: </span>
                  {triageResult.recommendation}
                </div>
                {triageResult.possible_causes && (
                  <div className="mb-2">
                    <span className="font-bold">Possible causes: </span>
                    {triageResult.possible_causes}
                  </div>
                )}
                {triageResult.first_aid && (
                  <div className="mb-2">
                    <span className="font-bold text-orange-600">First aid: </span>
                    {triageResult.first_aid}
                  </div>
                )}
                {triageResult.home_remedies && (
                  <div className="mb-2">
                    <span className="font-bold">Home remedies: </span>
                    {triageResult.home_remedies}
                  </div>
                )}
                {triageResult.specialist_type && (
                  <div className="mb-2">
                    <span className="font-bold text-indigo-500">See a: </span>
                    {triageResult.specialist_type}
                  </div>
                )}
                {triageResult.untreated_outcome && (
                  <div className="mb-2">
                    <span className="font-bold text-red-500">If left untreated: </span>
                    {triageResult.untreated_outcome}
                  </div>
                )}

                {/* Explainable AI layer (planning doc: patients and doctors
                    alike must be able to see the reasoning behind the AI's
                    conclusion, not just the conclusion itself). */}
                {triageResult.explanation && (
                  <div className="mt-3 border-t border-white/20 pt-3">
                    <button
                      onClick={() => setShowExplanation((v) => !v)}
                      className="w-full flex items-center justify-between text-sm font-bold text-teal-600 dark:text-teal-400"
                    >
                      <span className="flex items-center gap-2">
                        <Brain size={15} /> Why does the AI think this?
                        {typeof triageResult.confidence === "number" && (
                          <span className="text-xs font-semibold text-gray-500">
                            ({Math.round(triageResult.confidence * 100)}% confidence)
                          </span>
                        )}
                      </span>
                      <motion.span animate={{ rotate: showExplanation ? 180 : 0 }}>
                        <ChevronDown size={16} />
                      </motion.span>
                    </button>
                    <AnimatePresence initial={false}>
                      {showExplanation && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden"
                        >
                          <p className="text-sm text-gray-600 dark:text-gray-300 mt-2">
                            {triageResult.explanation}
                          </p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}

                {triageResult.severity === 'CRITICAL' && (
                  <div className="mt-3 p-3 rounded-xl bg-red-500/15 border border-red-500/40 text-sm font-semibold text-red-600">
                    ⚠ This looks like an emergency. Call 108 or use the Emergency SOS
                    in the GramCare mobile app immediately.
                  </div>
                )}

                {/* Inter-module connection (planning doc): the specialist
                    recommendation here feeds directly into doctor selection
                    on the booking page, and the severity score rides along
                    so the doctor's queue can be risk-sorted. */}
                <button
                  onClick={() => {
                    const params = new URLSearchParams({ symptoms });
                    if (triageResult.severity_score != null) params.set("severity", String(triageResult.severity_score));
                    if (triageResult.specialist_type) params.set("specialist", triageResult.specialist_type);
                    router.push(`/book?${params.toString()}`);
                  }}
                  className="neu-button w-full mt-4 py-3 bg-indigo-500 text-white font-bold rounded-xl flex items-center justify-center gap-2"
                >
                  <Stethoscope size={18} />
                  {triageResult.specialist_type ? `Book a ${triageResult.specialist_type}` : "Book a Consultation"}
                </button>
              </motion.div>
            )}
          </div>
        </motion.div>

        {/* Doctor Portal - Realtime Alert Feed */}
        <div className="flex flex-col h-full">
          <motion.div
            className="neu-panel p-6 flex flex-col h-full w-full relative overflow-hidden"
          >
            <div className="flex items-center mb-6">
              <div className="w-12 h-12 rounded-full bg-[var(--background)] shadow-[var(--shadow-neu-flat)] flex items-center justify-center mr-4 text-indigo-500 shrink-0">
                <ShieldAlert size={24} />
              </div>
              <div>
                <h2 className="text-xl font-bold">Doctor Portal Live Feed</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">Realtime WebSocket Triage Alerts</p>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4">
              {alerts.length === 0 ? (
                <div className="h-full flex items-center justify-center text-gray-400">
                  Waiting for incoming triage alerts...
                </div>
              ) : (
                alerts.map((alert, idx) => (
                  <motion.div
                    key={alert.id + idx}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={`p-4 rounded-xl border ${alert.isEmergency || alert.severity === 'CRITICAL' ? 'bg-red-500/10 border-red-500/30' : 'bg-[var(--background)] shadow-[var(--shadow-neu-flat)] border-transparent'}`}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-bold text-sm text-gray-500">{alert.time}</span>
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        alert.severity === 'CRITICAL' ? 'bg-red-500 text-white animate-pulse' :
                        alert.severity === 'HIGH' ? 'bg-orange-500 text-white' :
                        alert.severity === 'MODERATE' ? 'bg-yellow-500 text-black' :
                        'bg-green-500 text-white'
                      }`}>
                        {alert.severity}
                      </span>
                    </div>
                    <div className="font-semibold text-lg mb-1">{alert.department}</div>
                    <div className="text-sm text-gray-600 dark:text-gray-300">Symptoms: {alert.symptoms}</div>
                  </motion.div>
                ))
              )}
            </div>
          </motion.div>
        </div>

      </div>
    </div>
  );
}
