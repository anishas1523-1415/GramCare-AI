"use client";

// Preventive AI — rule-based screening/vaccination reminders. Backend is
// core/preventive_rules.py + modules/preventive/router.py: a deterministic
// ruleset over age/gender/chronic-conditions and existing EHR history, not
// a trained model (see that module's docstring). This page is the missing
// frontend for it — the backend had full test coverage before any UI
// called it.

import { motion } from "framer-motion";
import { ShieldCheck, Syringe, Stethoscope, FlaskConical, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useProfile } from "../../contexts/ProfileContext";
import { useLocale } from "../../contexts/LocaleContext";
import ThemedLoader from "../../components/ThemedLoader";
import api from "../../lib/api";
import type { PreventiveReminder } from "../../types";

export default function PreventiveCarePage() {
  const router = useRouter();
  const { t } = useLocale();
  const { profiles, activeProfile, setActiveProfile } = useProfile();
  const [reminders, setReminders] = useState<PreventiveReminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [includeUpcoming, setIncludeUpcoming] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<PreventiveReminder[]>("/preventive/reminders", {
        params: {
          family_profile_id: activeProfile?.id ?? undefined,
          include_upcoming: includeUpcoming,
        },
      });
      setReminders(res.data);
    } catch {
      setError(t('could_not_load_preventive'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProfile, includeUpcoming]);

  const act = (r: PreventiveReminder) => {
    if (r.suggested_action === "lab_test") {
      router.push("/lab-tests");
    } else {
      router.push("/book");
    }
  };

  return (
    <div className="min-h-screen p-6 lg:p-16 flex items-start justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-2xl w-full p-8"
      >
        <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
          <ShieldCheck className="text-emerald-500" /> {t('nav_preventive_care')}
        </h1>
        <p className="text-gray-500 mb-6">
          {t('preventive_care_subtitle')}
        </p>

        {profiles.length > 0 && (
          <div className="mb-4">
            <label className="text-sm font-semibold block mb-1.5">{t('acting_for')}</label>
            <select
              value={activeProfile?.id ?? ""}
              onChange={(e) => {
                const id = e.target.value;
                setActiveProfile(id === "" ? null : profiles.find((p) => p.id === Number(id)) || null);
              }}
              className="w-full p-2.5 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-emerald-400"
            >
              <option value="">{t('myself')}</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.full_name} ({p.relation})</option>
              ))}
            </select>
          </div>
        )}

        <label className="flex items-center gap-2 mb-6 text-sm text-gray-500 cursor-pointer">
          <input
            type="checkbox"
            checked={includeUpcoming}
            onChange={(e) => setIncludeUpcoming(e.target.checked)}
            className="w-4 h-4 accent-emerald-500"
          />
          {t('show_upcoming_toggle')}
        </label>

        {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

        {loading ? (
          <ThemedLoader variant="wallet" label={t('checking_preventive_schedule')} />
        ) : reminders.length === 0 ? (
          <p className="text-center text-gray-400 py-12">
            {includeUpcoming ? t('no_screenings_found') : t('nothing_due_now')}
          </p>
        ) : (
          <div className="space-y-3">
            {reminders.map((r) => (
              <button
                key={r.key}
                type="button"
                onClick={() => act(r)}
                className={`w-full text-left neu-panel p-4 flex items-center justify-between gap-3 hover:ring-2 transition-shadow ${
                  r.due ? "hover:ring-emerald-400/50" : "opacity-60 hover:ring-gray-400/40"
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`shrink-0 w-10 h-10 rounded-xl flex items-center justify-center ${r.category === "vaccination" ? "bg-indigo-500/15 text-indigo-500" : "bg-emerald-500/15 text-emerald-500"}`}>
                    {r.category === "vaccination" ? <Syringe size={18} /> : <Stethoscope size={18} />}
                  </div>
                  <div>
                    <p className="font-bold flex items-center gap-2">
                      {r.title}
                      {!r.due && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-400/15 text-gray-400">{t('upcoming_badge')}</span>}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">{r.reason}</p>
                    {r.last_done_date && (
                      <p className="text-xs text-gray-400 mt-1">Last recorded: {new Date(r.last_done_date).toLocaleDateString()}</p>
                    )}
                    <p className="text-xs font-semibold text-emerald-500 mt-1 flex items-center gap-1">
                      {r.suggested_action === "lab_test" ? <FlaskConical size={12} /> : <Stethoscope size={12} />}
                      {r.suggested_action === "lab_test" ? t('book_a_lab_test') : t('book_a_consultation')}
                    </p>
                  </div>
                </div>
                <ChevronRight size={18} className="text-gray-400 shrink-0" />
              </button>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
