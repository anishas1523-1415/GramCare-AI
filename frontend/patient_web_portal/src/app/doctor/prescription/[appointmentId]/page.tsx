"use client";

import React, { use, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, Plus, Trash2, Printer, CheckCircle2, TriangleAlert, ShieldAlert, Brain, ChevronDown, Mic, MicOff } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import api from '../../../../lib/api';
import { useLocale } from '../../../../contexts/LocaleContext';
import type { InteractionWarning, CdsAlert } from '../../../../types';

// Shared severity -> color mapping, matching the CRITICAL/HIGH/MODERATE/LOW
// convention used by the symptom-checker's triage badges (see
// app/symptom-checker/page.tsx), collapsed onto the CDS module's 3-level
// INFO/WARNING/CRITICAL scale.
const CDS_SEVERITY_CLASSES: Record<string, string> = {
  CRITICAL: 'bg-red-500 text-white',
  WARNING: 'bg-orange-500 text-white',
  INFO: 'bg-yellow-500 text-black',
};

const CDS_CATEGORY_KEY: Record<string, string> = {
  INTERACTION: 'cds_category_interaction',
  ALLERGY: 'cds_category_allergy',
  DUPLICATE_THERAPY: 'cds_category_duplicate_therapy',
  DOSAGE_CHANGE: 'cds_category_dosage_change',
};

// Next.js 15+ (this project is on Next 16.2.9) passes `params` as a Promise
// on page components, not a plain object. The previous synchronous
// destructuring (`{ params }: { params: { appointmentId: string } }`)
// worked on older Next.js but throws/warns on this version — must unwrap
// with `use()`.
export default function PrescriptionWriter({ params }: { params: Promise<{ appointmentId: string }> }) {
  const { appointmentId } = use(params);
  const router = useRouter();
  const { t } = useLocale();
  const searchParams = useSearchParams();
  // Previously hardcoded to patient_id: 1 on submit regardless of which
  // patient the appointment was actually for. The doctor dashboard now
  // passes the real patient_id as a query param when linking here (see
  // doctor/dashboard/page.tsx), since there is no GET /appointments/{id}
  // single-fetch endpoint to look it up from appointmentId alone.
  const patientIdParam = searchParams.get('patient_id');
  const patientId = patientIdParam ? parseInt(patientIdParam, 10) : null;
  const [loading, setLoading] = useState(false);
  const [diagnosis, setDiagnosis] = useState('');
  const [notes, setNotes] = useState('');
  const [medicines, setMedicines] = useState([
    { name: '', dosage: '', frequency: '1-0-1', duration: '5 days' }
  ]);

  // Clinical Decision Support — a doctor can run this any time while
  // editing (advisory, not blocking submission): combines the existing
  // drug-interaction check with three more heuristics (allergy conflict,
  // duplicate therapy, dosage-sanity) against this patient's records. Every
  // alert carries its own `explanation` (Explainable AI), shown behind a
  // "Why?" toggle rather than always-expanded so the list stays scannable.
  const [cdsAlerts, setCdsAlerts] = useState<CdsAlert[]>([]);
  const [cdsChecked, setCdsChecked] = useState(false);
  const [checkingCds, setCheckingCds] = useState(false);
  const [cdsError, setCdsError] = useState('');
  const [expandedAlert, setExpandedAlert] = useState<number | null>(null);

  // Dictation / Voice-to-Text state
  const [isDictating, setIsDictating] = useState(false);
  const [dictationError, setDictationError] = useState('');
  const [isParsingDictation, setIsParsingDictation] = useState(false);
  const recognitionRef = React.useRef<any>(null);

  React.useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      let fullTranscript = '';
      
      recognitionRef.current.onresult = (event: any) => {
        let currentTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            fullTranscript += event.results[i][0].transcript + ' ';
          } else {
            currentTranscript += event.results[i][0].transcript;
          }
        }
        // Update the notes field with the live transcript temporarily so the doctor sees it
        if (event.results[event.results.length - 1].isFinal) {
          setNotes(prev => (prev + ' ' + event.results[event.results.length - 1][0].transcript).trim());
        }
      };

      recognitionRef.current.onerror = (event: any) => {
        if (event.error !== 'no-speech') {
          setDictationError(t('dictation_error_prefix') + ' ' + event.error);
          setIsDictating(false);
        }
      };

      recognitionRef.current.onend = () => {
        setIsDictating(false);
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleDictation = async () => {
    if (!recognitionRef.current) {
      setDictationError(t('voice_dictation_not_supported'));
      return;
    }
    setDictationError('');

    if (isDictating) {
      recognitionRef.current.stop();
      setIsDictating(false);
      
      // Parse what was dictated using AI
      if (notes.trim()) {
        setIsParsingDictation(true);
        try {
          // Send the entire notes field (which contains the dictation) to the AI parser
          // Mounted at /assist, not /ai-assist (main.py's include_router
          // prefix) — the old path 404'd, so dictation always failed.
          const res = await api.post('/assist/parse-prescription', {
            dictation_text: notes
          });
          const parsed = res.data;
          
          if (parsed.diagnosis) setDiagnosis(parsed.diagnosis);
          if (parsed.notes) setNotes(parsed.notes);
          
          if (parsed.medicines && parsed.medicines.length > 0) {
            setMedicines(parsed.medicines);
            setCdsChecked(false);
          }
        } catch (err) {
          setDictationError(t('dictation_ai_parse_failed'));
        } finally {
          setIsParsingDictation(false);
        }
      }
    } else {
      try {
        recognitionRef.current.start();
        setIsDictating(true);
      } catch (e) {
        // Already started
      }
    }
  };

  const addMedicine = () => {
    setMedicines([...medicines, { name: '', dosage: '', frequency: '1-0-1', duration: '5 days' }]);
    setCdsChecked(false);
  };

  const removeMedicine = (index: number) => {
    setMedicines(medicines.filter((_, i) => i !== index));
    setCdsChecked(false);
  };

  const updateMedicine = (index: number, field: string, value: string) => {
    const updated = [...medicines];
    updated[index] = { ...updated[index], [field]: value };
    setMedicines(updated);
    if (field === 'name' || field === 'dosage') setCdsChecked(false);
  };

  const runCdsCheck = async () => {
    if (!patientId) {
      setCdsError(t('missing_patient_info_appointment'));
      return;
    }
    const named = medicines.filter((m) => m.name.trim());
    if (named.length === 0) return;

    setCheckingCds(true);
    setCdsError('');
    setExpandedAlert(null);
    try {
      const res = await api.post<{ alerts: CdsAlert[] }>('/cds/check', {
        patient_id: patientId,
        medicines: named.map((m) => ({ name: m.name, dosage: m.dosage })),
      });
      setCdsAlerts(res.data.alerts);
      setCdsChecked(true);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setCdsError(typeof detail === 'string' ? detail : t('could_not_run_safety_check'));
    } finally {
      setCheckingCds(false);
    }
  };

  const [submitError, setSubmitError] = useState('');
  const [issued, setIssued] = useState(false);
  const [interactionWarnings, setInteractionWarnings] = useState<InteractionWarning[]>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError('');

    if (!patientId) {
      setSubmitError(t('missing_patient_info_full'));
      return;
    }

    setLoading(true);

    try {
      const res = await api.post('/ehr/issue_prescription', {
        appointment_id: parseInt(appointmentId, 10),
        patient_id: patientId,
        medicines: medicines,
        diagnosis,
        notes,
        dosage_instructions: "Follow strictly after meals unless specified."
      });
      // Medicine Interaction Alerts (planning doc): checked server-side
      // against the patient's other currently-active medicines.
      setInteractionWarnings(res.data?.interaction_warnings || []);
      setIssued(true);
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setSubmitError(detail || t('failed_issue_prescription'));
    } finally {
      setLoading(false);
    }
  };

  if (issued) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-panel max-w-lg w-full p-8 text-center"
        >
          <CheckCircle2 size={56} className="text-emerald-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">{t('prescription_issued')}</h2>
          <p className="text-gray-500 mb-6">
            {t('prescription_issued_note')}
          </p>

          {interactionWarnings.length > 0 && (
            <div className="text-left mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/40">
              <p className="font-bold text-red-600 flex items-center gap-2 mb-2">
                <TriangleAlert size={18} /> {t('medicine_interaction_warning')}
              </p>
              {interactionWarnings.map((w, i) => (
                <p key={i} className="text-sm text-red-700 dark:text-red-300 mb-1">
                  <strong>{w.drug_a} + {w.drug_b}</strong> ({w.severity}): {w.description}
                </p>
              ))}
            </div>
          )}

          <button
            onClick={() => router.push('/doctor/dashboard')}
            className="neu-button w-full py-3 bg-teal-500 text-white font-bold rounded-xl"
          >
            {t('back_to_dashboard')}
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-24 relative overflow-hidden bg-[var(--background)]">
      <div className="absolute top-[20%] left-[-10%] w-[500px] h-[500px] bg-indigo-500 rounded-full mix-blend-multiply filter blur-[100px] opacity-10 -z-10" />

      <div className="max-w-4xl mx-auto">
        <header className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3"><FileText className="text-indigo-500" /> {t('digital_prescription_title')}</h1>
            <p className="text-gray-500 mt-1">{t('appointment_hash')}{appointmentId}</p>
          </div>
          <button className="neu-button px-4 py-2 flex items-center gap-2 font-bold text-gray-700 dark:text-gray-200">
            <Printer size={18} /> {t('print_btn')}
          </button>
        </header>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="glass-panel p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">{t('diagnosis_notes_title')}</h2>
              <button
                type="button"
                onClick={toggleDictation}
                disabled={isParsingDictation}
                className={`px-4 py-2 rounded-lg flex items-center gap-2 font-bold transition-colors ${
                  isDictating 
                    ? 'bg-red-500 text-white animate-pulse' 
                    : 'bg-indigo-500/10 text-indigo-500 hover:bg-indigo-500 hover:text-white'
                }`}
              >
                {isDictating ? <Mic size={18} /> : <MicOff size={18} />}
                {isDictating ? t('dictating_ellipsis') : isParsingDictation ? t('parsing_ai_ellipsis') : t('voice_dictate_btn')}
              </button>
            </div>
            {dictationError && <p className="text-red-500 text-sm font-semibold mb-3">{dictationError}</p>}
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="rx-diagnosis" className="block text-sm font-semibold mb-2">{t('primary_diagnosis_label')}</label>
                <input
                  id="rx-diagnosis"
                  required
                  type="text"
                  value={diagnosis}
                  onChange={e => setDiagnosis(e.target.value)}
                  placeholder="e.g. Viral Infection"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>
              <div>
                <label htmlFor="rx-notes" className="block text-sm font-semibold mb-2">{t('clinical_notes_label')}</label>
                <textarea
                  id="rx-notes"
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="Additional observations..."
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
                  rows={2}
                />
              </div>
            </div>
          </div>

          <div className="glass-panel p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold">{t('medicines_title')}</h2>
              <button
                type="button"
                onClick={addMedicine}
                className="px-4 py-2 bg-indigo-500/10 text-indigo-500 font-bold rounded-lg flex items-center gap-2 hover:bg-indigo-500 hover:text-white transition-colors"
              >
                <Plus size={16} /> {t('add_medicine_btn')}
              </button>
            </div>

            <div className="space-y-4">
              {medicines.map((med, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end bg-white/40 dark:bg-black/40 p-4 rounded-xl border border-white/20 relative"
                >
                  <div className="md:col-span-4">
                    <label htmlFor={`med-name-${index}`} className="block text-xs font-semibold mb-1 text-gray-500">{t('medicine_name_label')}</label>
                    <input
                      id={`med-name-${index}`}
                      required
                      type="text"
                      value={med.name}
                      onChange={e => updateMedicine(index, 'name', e.target.value)}
                      placeholder="e.g. Paracetamol"
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label htmlFor={`med-dosage-${index}`} className="block text-xs font-semibold mb-1 text-gray-500">{t('dosage_label')}</label>
                    <input
                      id={`med-dosage-${index}`}
                      required
                      type="text"
                      value={med.dosage}
                      onChange={e => updateMedicine(index, 'dosage', e.target.value)}
                      placeholder="500mg"
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none"
                    />
                  </div>
                  <div className="md:col-span-3">
                    <label htmlFor={`med-frequency-${index}`} className="block text-xs font-semibold mb-1 text-gray-500">{t('frequency_label')}</label>
                    <select
                      id={`med-frequency-${index}`}
                      value={med.frequency}
                      onChange={e => updateMedicine(index, 'frequency', e.target.value)}
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none"
                    >
                      <option>1-0-1 (Morning & Night)</option>
                      <option>1-1-1 (Three times a day)</option>
                      <option>1-0-0 (Morning only)</option>
                      <option>0-0-1 (Night only)</option>
                      <option>SOS (As needed)</option>
                    </select>
                  </div>
                  <div className="md:col-span-2">
                    <label htmlFor={`med-duration-${index}`} className="block text-xs font-semibold mb-1 text-gray-500">{t('duration_label')}</label>
                    <input
                      id={`med-duration-${index}`}
                      required
                      type="text"
                      value={med.duration}
                      onChange={e => updateMedicine(index, 'duration', e.target.value)}
                      placeholder="5 days"
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none"
                    />
                  </div>
                  <div className="md:col-span-1 flex justify-end">
                    <button
                      type="button"
                      onClick={() => removeMedicine(index)}
                      disabled={medicines.length === 1}
                      className="p-2 bg-red-500/10 text-red-500 rounded-lg hover:bg-red-500 hover:text-white transition-colors disabled:opacity-30"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Clinical Decision Support — advisory safety check, run
                on-demand rather than automatically on every keystroke. */}
            <div className="mt-6 pt-6 border-t border-white/10">
              <button
                type="button"
                onClick={runCdsCheck}
                disabled={checkingCds || !patientId}
                className="w-full py-3 rounded-xl border-2 border-indigo-500/40 text-indigo-500 font-bold flex items-center justify-center gap-2 hover:bg-indigo-500/10 transition-colors disabled:opacity-50"
              >
                <ShieldAlert size={18} />
                {checkingCds ? t('checking_safety_ellipsis') : t('check_safety_interactions_btn')}
              </button>
              {cdsError && <p role="alert" className="text-red-500 text-sm font-semibold mt-3">{cdsError}</p>}

              {cdsChecked && (
                <div className="mt-4 space-y-2">
                  {cdsAlerts.length === 0 ? (
                    <p className="text-sm text-emerald-500 font-semibold flex items-center gap-2">
                      <CheckCircle2 size={16} /> {t('no_cds_issues_found')}
                    </p>
                  ) : (
                    cdsAlerts.map((alert, i) => (
                      <div key={i} className="rounded-xl bg-white/40 dark:bg-black/40 border border-white/20 overflow-hidden">
                        <div className="p-3 flex items-start gap-3">
                          <span className={`shrink-0 px-2 py-1 rounded text-xs font-bold ${CDS_SEVERITY_CLASSES[alert.severity]}`}>
                            {alert.severity}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">{CDS_CATEGORY_KEY[alert.category] ? t(CDS_CATEGORY_KEY[alert.category]) : alert.category}</p>
                            <p className="text-sm font-semibold">{alert.message}</p>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setExpandedAlert(expandedAlert === i ? null : i)}
                          className="w-full flex items-center justify-between px-3 py-2 text-xs font-bold text-indigo-500 border-t border-white/10"
                        >
                          <span className="flex items-center gap-1.5"><Brain size={13} /> {t('why_flagged')}</span>
                          <motion.span animate={{ rotate: expandedAlert === i ? 180 : 0 }}>
                            <ChevronDown size={14} />
                          </motion.span>
                        </button>
                        <AnimatePresence initial={false}>
                          {expandedAlert === i && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <p className="px-3 pb-3 text-sm text-gray-600 dark:text-gray-300">{alert.explanation}</p>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          {submitError && (
            <p role="alert" className="text-red-500 text-sm font-semibold text-right">{submitError}</p>
          )}

          <div className="flex justify-end pt-4">
            <button
              type="submit"
              disabled={loading}
              className="neu-button px-10 py-4 bg-teal-500 text-white font-bold rounded-xl text-lg disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? t('sending_ellipsis') : t('issue_eprescription_btn')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
