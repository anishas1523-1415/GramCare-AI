"use client";

// Patient-facing Emergency SOS. The backend (modules/emergency/router.py,
// mounted at /api/v1/sos) has fully supported this since it was built —
// POST /sos/trigger assigns the nearest hospital immediately, plus a
// background escalation loop (main.py's _sos_escalation_loop) reassigns
// unanswered alerts — and the Flutter patient app has a complete SOS flow
// (sos_service.dart, sos_active_screen.dart). web_portal had none of it:
// the only "emergency" references in the whole app were the hospital/
// doctor RECEIVING side (hospital/page.tsx's Emergency Desk), never a
// patient TRIGGER. This page is that missing trigger.

import { motion } from "framer-motion";
import { ShieldAlert, MapPin, Phone, Plus, Trash2, Clock, CheckCircle2, AlertTriangle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useProfile } from "../../contexts/ProfileContext";
import { useLocale } from "../../contexts/LocaleContext";
import api from "../../lib/api";
import type { EmergencySOS, EmergencyContact } from "../../types";

function getBestEffortLocation(unavailableText: string): Promise<{ lat: number | null; lng: number | null; text: string }> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      resolve({ lat: null, lng: null, text: unavailableText });
      return;
    }
    const timeout = setTimeout(() => resolve({ lat: null, lng: null, text: unavailableText }), 5000);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        clearTimeout(timeout);
        resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude, text: "GPS location captured" });
      },
      () => {
        clearTimeout(timeout);
        resolve({ lat: null, lng: null, text: unavailableText });
      },
      { enableHighAccuracy: true, timeout: 4500 }
    );
  });
}

export default function SosPage() {
  const { user } = useAuth();
  const { profiles, activeProfile } = useProfile();
  const { t } = useLocale();

  const STATUS_META: Record<EmergencySOS["status"], { label: string; cls: string }> = {
    ACTIVE: { label: t('sos_waiting_response'), cls: "bg-red-500/15 text-red-500 border-red-500/30" },
    RESPONDED: { label: t('sos_help_on_way'), cls: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30" },
    RESOLVED: { label: t('sos_resolved'), cls: "bg-gray-500/15 text-gray-400 border-gray-500/30" },
  };

  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const [forProfileId, setForProfileId] = useState<number | "">(activeProfile?.id ?? "");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const [history, setHistory] = useState<EmergencySOS[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [addingContact, setAddingContact] = useState(false);
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactRelation, setContactRelation] = useState("");

  const active = history.find((s) => s.status === "ACTIVE" || s.status === "RESPONDED");

  const loadHistory = async () => {
    try {
      const res = await api.get<EmergencySOS[]>("/sos/mine");
      setHistory(res.data);
    } catch {
      // silent — this is a background refresh, not a user-initiated action
    } finally {
      setHistoryLoading(false);
    }
  };

  const loadContacts = async () => {
    try {
      const res = await api.get<EmergencyContact[]>("/sos/contacts");
      setContacts(res.data);
    } catch {
      // non-critical section, fail quietly
    }
  };

  useEffect(() => {
    if (!user) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadHistory();
    void loadContacts();
  }, [user]);

  useEffect(() => {
    if (active) {
      pollRef.current = setInterval(loadHistory, 6000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.status]);

  const sendSos = async () => {
    setSending(true);
    setError("");
    try {
      const loc = await getBestEffortLocation(t('location_unavailable'));
      await api.post("/sos/trigger", {
        location_lat: loc.lat,
        location_lng: loc.lng,
        location_text: loc.text,
        voice_note: note || null,
        severity: "CRITICAL",
        family_profile_id: forProfileId === "" ? null : forProfileId,
      });
      setConfirming(false);
      setNote("");
      await loadHistory();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === "string" ? message : t('sos_send_failed'));
    } finally {
      setSending(false);
    }
  };

  const resolveSos = async (id: number) => {
    try {
      await api.put(`/sos/${id}/resolve`);
      loadHistory();
    } catch {
      setError(t('sos_update_failed'));
    }
  };

  const addContact = async () => {
    if (!contactName || !contactPhone) return;
    setAddingContact(true);
    try {
      await api.post("/sos/contacts", { name: contactName, phone: contactPhone, relation: contactRelation || null });
      setContactName("");
      setContactPhone("");
      setContactRelation("");
      loadContacts();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === "string" ? message : t('sos_contact_save_failed'));
    } finally {
      setAddingContact(false);
    }
  };

  const removeContact = async (id: number) => {
    try {
      await api.delete(`/sos/contacts/${id}`);
      loadContacts();
    } catch {
      setError(t('sos_contact_remove_failed'));
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">{t('please_login_sos')}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 lg:p-16 flex items-start justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-2xl w-full p-8 relative overflow-hidden border-2 border-red-500/20"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-red-500/10 to-orange-400/5 z-0" />
        <div className="relative z-10">
          <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
            <ShieldAlert className="text-red-500" /> {t('emergency_sos')}
          </h1>
          <p className="text-gray-500 mb-8">
            {t('sos_page_subtitle')}
          </p>

          {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

          {active ? (
            <div className="mb-8 p-5 rounded-2xl border-2 border-red-500/30 bg-red-500/5">
              <div className="flex items-center justify-between mb-3">
                <span className={`px-3 py-1 rounded-full text-xs font-bold border ${STATUS_META[active.status].cls} ${active.status === "ACTIVE" ? "animate-pulse" : ""}`}>
                  {STATUS_META[active.status].label}
                </span>
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <Clock size={12} /> {new Date(active.created_at).toLocaleTimeString()}
                </span>
              </div>
              {active.location_text && (
                <p className="text-sm text-gray-500 flex items-center gap-1.5 mb-3">
                  <MapPin size={14} /> {active.location_text}
                </p>
              )}
              {/* No approved hospital could take this alert. Showing the
                  normal "waiting" state here would imply someone is coming
                  when nobody was ever paged. */}
              {active.unrouted_reason && (
                <div className="mb-3 p-3 rounded-xl bg-red-600/15 border-2 border-red-600/60 flex items-start gap-2">
                  <AlertTriangle size={18} className="text-red-500 mt-0.5 shrink-0" />
                  <div className="text-sm text-left">
                    <p className="font-bold text-red-500">No hospital has received this alert</p>
                    <p className="text-gray-600 dark:text-gray-300">{active.unrouted_reason}</p>
                    <a href="tel:108" className="inline-block mt-2 px-4 py-2 rounded-lg bg-red-600 text-white font-bold text-sm">
                      Call 108 now
                    </a>
                  </div>
                </div>
              )}
              <button
                type="button"
                onClick={() => resolveSos(active.id)}
                className="neu-button w-full py-2.5 text-sm font-bold rounded-xl"
              >
                {t('im_safe_mark_resolved')}
              </button>
            </div>
          ) : !confirming ? (
            <motion.button
              type="button"
              onClick={() => setConfirming(true)}
              whileTap={{ scale: 0.97 }}
              animate={{ boxShadow: ["0 0 0 0 rgba(239,68,68,0.4)", "0 0 0 16px rgba(239,68,68,0)"] }}
              transition={{ duration: 1.8, repeat: Infinity }}
              className="w-full py-8 mb-8 rounded-2xl bg-red-500 text-white font-extrabold text-2xl flex items-center justify-center gap-3"
            >
              <ShieldAlert size={32} /> {t('trigger_sos')}
            </motion.button>
          ) : (
            <div className="mb-8 p-5 rounded-2xl border-2 border-red-500/30 bg-red-500/5">
              <p className="font-bold mb-4">{t('sos_confirm_prompt')}</p>

              {profiles.length > 0 && (
                <div className="mb-3">
                  <label className="text-sm font-semibold block mb-1.5">{t('who_needs_help')}</label>
                  <select
                    value={forProfileId}
                    onChange={(e) => setForProfileId(e.target.value === "" ? "" : Number(e.target.value))}
                    className="w-full p-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-red-400"
                  >
                    <option value="">{t('myself')}</option>
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>{p.full_name} ({p.relation})</option>
                    ))}
                  </select>
                </div>
              )}

              <textarea
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t('whats_happening_optional')}
                className="w-full p-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-red-400 resize-none mb-4"
              />

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  disabled={sending}
                  className="flex-1 neu-button py-3 font-bold rounded-xl disabled:opacity-50"
                >
                  {t('cancel')}
                </button>
                <button
                  type="button"
                  onClick={sendSos}
                  disabled={sending}
                  className="flex-1 py-3 bg-red-500 text-white font-bold rounded-xl disabled:opacity-50"
                >
                  {sending ? t('sending_ellipsis') : t('confirm_and_send')}
                </button>
              </div>
            </div>
          )}

          {/* Emergency contacts */}
          <div className="mb-8">
            <h2 className="text-lg font-bold mb-3 flex items-center gap-2">
              <Phone size={18} className="text-red-500" /> {t('emergency_contacts')}
            </h2>
            <p className="text-xs text-gray-400 mb-3">{t('emergency_contacts_note')}</p>
            <div className="space-y-2 mb-3">
              {contacts.map((c) => (
                <div key={c.id} className="flex items-center justify-between neu-panel p-3">
                  <div>
                    <p className="font-semibold text-sm">{c.name} {c.relation ? `(${c.relation})` : ""}</p>
                    <p className="text-xs text-gray-500">{c.phone}</p>
                  </div>
                  <button type="button" onClick={() => removeContact(c.id)} className="text-gray-400 hover:text-red-500 p-1.5">
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
              {contacts.length === 0 && (
                <p className="text-sm text-gray-400">{t('no_emergency_contacts')}</p>
              )}
            </div>
            {contacts.length < 5 && (
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="text"
                  placeholder={t('name')}
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  className="flex-1 p-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                />
                <input
                  type="tel"
                  placeholder={t('phone')}
                  value={contactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                  className="flex-1 p-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                />
                <input
                  type="text"
                  placeholder={t('relation')}
                  value={contactRelation}
                  onChange={(e) => setContactRelation(e.target.value)}
                  className="sm:w-28 p-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                />
                <button
                  type="button"
                  onClick={addContact}
                  disabled={addingContact || !contactName || !contactPhone}
                  className="neu-button px-4 py-2.5 rounded-xl disabled:opacity-50"
                >
                  <Plus size={16} />
                </button>
              </div>
            )}
          </div>

          {/* History */}
          {!historyLoading && history.filter((s) => s.status === "RESOLVED").length > 0 && (
            <div>
              <h2 className="text-lg font-bold mb-3">{t('past_alerts')}</h2>
              <div className="space-y-2">
                {history.filter((s) => s.status === "RESOLVED").slice(0, 5).map((s) => (
                  <div key={s.id} className="flex items-center justify-between neu-panel p-3 text-sm">
                    <span className="flex items-center gap-2 text-gray-500">
                      <CheckCircle2 size={14} className="text-emerald-500" />
                      {new Date(s.created_at).toLocaleString()}
                    </span>
                    <span className="text-xs text-gray-400">{s.location_text || "—"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
