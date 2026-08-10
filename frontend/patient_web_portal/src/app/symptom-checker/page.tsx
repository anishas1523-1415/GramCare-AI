"use client";

// The AI Symptom Checker, relocated off the homepage (which is now a
// branding/feature showcase — see ../page.tsx) to its own dedicated route.
// Functionality is unchanged from its original homepage incarnation: same
// triage call, same booking hand-off, same live-alert emit to the doctor
// dashboard's own socket feed.

import { motion, AnimatePresence } from "framer-motion";
import { Activity, Brain, ChevronDown, Stethoscope, Camera, X, ArrowLeft, WifiOff, Mic, MicOff } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { io } from "socket.io-client";
import api from "../../lib/api";
import { useProfile } from "../../contexts/ProfileContext";
import { useLocale } from "../../contexts/LocaleContext";
import { offlineTriageEstimate } from "../../lib/offlineTriage";

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

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "https://gramcare-signaling.onrender.com";

export default function SymptomCheckerPage() {
  const { activeProfile } = useProfile();
  const { t } = useLocale();
  const router = useRouter();
  const [symptoms, setSymptoms] = useState("");
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showExplanation, setShowExplanation] = useState(false);
  const [symptomImage, setSymptomImage] = useState<{ preview: string; base64: string } | null>(null);
  // True when `triageResult` came from the offline keyword-matching
  // fallback (no network reached /triage/analyze) rather than the real AI.
  const [isOfflineEstimate, setIsOfflineEstimate] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [speechError, setSpeechError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    // Initialize Web Speech API
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      // Let the browser auto-detect the language based on the user's speech,
      // or we could lock it to Tamil/English based on LocaleContext.
      // For now, leaving it empty lets the OS handle it best.
      
      recognitionRef.current.onresult = (event: any) => {
        let finalTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setSymptoms((prev) => prev + (prev.length > 0 && !prev.endsWith(" ") ? " " : "") + finalTranscript);
        }
      };

      recognitionRef.current.onerror = (event: any) => {
        if (event.error !== "no-speech") {
          setSpeechError("Speech recognition error: " + event.error);
          setIsListening(false);
        }
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }
  }, []);

  const toggleListening = () => {
    if (!recognitionRef.current) {
      setSpeechError("Voice input is not supported in this browser.");
      return;
    }
    setSpeechError("");
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (e) {
        // Already started
      }
    }
  };

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

  const analyzeSymptoms = async () => {
    if (!symptoms.trim()) return;

    setLoading(true);
    setError("");
    setTriageResult(null);
    setShowExplanation(false);
    setIsOfflineEstimate(false);

    try {
      const res = await api.post("/triage/analyze", {
        symptoms_text: symptoms,
        patient_id: "GUEST",
        age: activeProfile?.age ?? 30,
        family_profile_id: activeProfile?.id ?? null,
        image_base64: symptomImage?.base64 ?? null,
      });

      const data = res.data;

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

      // Emit the triage alert to the WebSocket server for the doctor
      // dashboard's own live feed (see doctor/dashboard/page.tsx).
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
      // Mirror the exact network-vs-server-error distinction used in
      // ../login/page.tsx's handleSubmit catch block: a `.response` means
      // the server actually answered (a real error to show as-is); a
      // `.request` with no `.response` means the request went out but
      // nothing ever came back — no connectivity, a dropped connection, or
      // a cold-starting backend. Only that second case falls back to the
      // offline estimate; a real server-side error should stay a real error.
      const axiosErr = err as { response?: unknown; request?: unknown };
      if (!axiosErr?.response && axiosErr?.request) {
        const offline = offlineTriageEstimate(symptoms);
        if (offline) {
          setTriageResult({
            severity: offline.severity,
            department: offline.department,
            recommendation: offline.recommendation,
          });
          setIsOfflineEstimate(true);
        } else {
          setError(
            "You appear to be offline, and this couldn't produce even an offline estimate for these symptoms. If you're at all concerned, please seek care or call your local emergency number."
          );
        }
      } else {
        setError(err instanceof Error ? err.message : "An error occurred");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center p-6 lg:p-16 relative overflow-hidden">
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

      <div className="w-full max-w-2xl mb-6">
        <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-gray-500 hover:text-teal-500 transition-colors">
          <ArrowLeft size={16} /> {t('back_to_home')}
        </Link>
      </div>

      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="text-center mb-10 max-w-xl"
      >
        <h1 className="text-3xl lg:text-4xl font-extrabold tracking-tight mb-3 text-[var(--foreground)]">
          {t('symptom_checker_title')}
        </h1>
        <p className="text-gray-500 dark:text-gray-400">
          {t('symptom_checker_page_subtitle')}
        </p>
      </motion.div>

      <motion.div
        className="glass-panel p-8 flex flex-col items-center justify-center text-center relative overflow-hidden w-full max-w-xl"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/10 to-teal-400/10 z-0"></div>

        <div className="z-10 w-full">
          <div className="w-16 h-16 mx-auto rounded-xl bg-white/20 backdrop-blur-md border border-white/30 flex items-center justify-center mb-6 text-teal-400">
            <Activity size={32} />
          </div>

          <div className="relative mb-4">
            <textarea
              className="w-full p-4 pr-12 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-teal-400 resize-none"
              rows={4}
              placeholder={t('symptom_checker_placeholder')}
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
            />
            <button
              onClick={toggleListening}
              className={`absolute right-3 bottom-3 p-2 rounded-full transition-colors ${
                isListening ? "bg-red-500 text-white animate-pulse" : "bg-teal-500/20 text-teal-600 dark:text-teal-400 hover:bg-teal-500/40"
              }`}
              title="Dictate symptoms"
            >
              {isListening ? <Mic size={20} /> : <MicOff size={20} />}
            </button>
          </div>
          {speechError && <p className="text-red-500 text-xs mb-3">{speechError}</p>}

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
              <Camera size={16} /> {t('add_symptom_photo')}
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
                <span>{t('ai_thinking')}</span>
              </>
            ) : (
              t('analyze_with_ai')
            )}
          </button>

          {error && <p className="text-red-500 mt-4 text-sm font-semibold">{error}</p>}

          {isOfflineEstimate && triageResult && (
            <div className="mt-6 p-3.5 rounded-xl bg-amber-500/15 border-2 border-amber-500/70 text-left flex items-start gap-2.5">
              <WifiOff size={20} className="text-amber-600 dark:text-amber-400 mt-0.5 flex-shrink-0" />
              <p className="text-sm font-bold text-amber-700 dark:text-amber-400">
                Offline estimate — not a full AI analysis. This is only a basic keyword-based
                safety check because we couldn&apos;t reach the server. Connect to the internet
                when possible, and seek care immediately if this feels serious.
              </p>
            </div>
          )}

          {triageResult && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`p-4 rounded-xl bg-white/40 dark:bg-black/40 border text-left ${
                isOfflineEstimate ? "mt-3 border-amber-500/40" : "mt-6 border-white/20"
              }`}
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
    </div>
  );
}
