"use client";

import { motion } from "framer-motion";
import { Activity, ShieldAlert, Radio } from "lucide-react";
import { useState, useEffect } from "react";
import { io } from "socket.io-client";
import api from "../lib/api";

export default function Home() {
  const [symptoms, setSymptoms] = useState("");
  const [triageResult, setTriageResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  
  // Realtime Socket State
  const [alerts, setAlerts] = useState<any[]>([]);
  const [socketConnected, setSocketConnected] = useState(false);

  const WS_URL_EFFECT = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:4000";

  useEffect(() => {
    // Connect to Node.js Realtime Server
    const socket = io(WS_URL_EFFECT);

    socket.on("connect", () => {
      setSocketConnected(true);
      // Join General Medicine department for demo
      socket.emit("join_department", "General Medicine");
    });

    socket.on("disconnect", () => {
      setSocketConnected(false);
    });

    // Listen for triage updates (simulated emergency alerts)
    socket.on("triage_update", (data) => {
      setAlerts((prev) => [data, ...prev].slice(0, 5)); // Keep last 5
    });

    socket.on("emergency_alert", (data) => {
      setAlerts((prev) => [{ ...data, isEmergency: true }, ...prev].slice(0, 5));
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:4000";

  const analyzeSymptoms = async () => {
    if (!symptoms.trim()) return;
    
    setLoading(true);
    setError("");
    setTriageResult(null);

    try {
      // Connect to the FastAPI Backend (unified API)
      const res = await api.post("/triage/analyze", {
        symptoms_text: symptoms,
        patient_id: "GUEST",
        age: 30,
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

    } catch (err: any) {
      setError(err.message || "An error occurred");
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
            
            <button
              onClick={analyzeSymptoms}
              disabled={loading || !symptoms.trim()}
              className="neu-button w-full py-3 bg-teal-500 text-white flex items-center justify-center disabled:opacity-50"
            >
              {loading ? <span className="animate-pulse">Analyzing...</span> : "Analyze with AI"}
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
