"use client";

// Landing view. Previously this page doubled as a live AI Symptom Checker +
// a "Doctor Portal Live Feed" (the latter fully duplicated the doctor
// dashboard's own socket feed — see doctor/dashboard/page.tsx). The checker
// itself moved to its own /symptom-checker route (a real feature, just not
// homepage clutter); the duplicate feed was dropped entirely. This is now a
// branding + feature showcase for the GramCare AI name/mission.

import { motion, AnimatePresence } from "framer-motion";
import {
  Radio, Brain, ShieldAlert, Users, Video, MessageSquareText, Globe, Sparkles,
  ArrowRight, ChevronLeft, ChevronRight,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { io } from "socket.io-client";
import { useAuth } from "../contexts/AuthContext";
import { useLocale } from "../contexts/LocaleContext";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "https://gramcare-signaling.onrender.com";

interface Feature {
  icon: ReactNode;
  titleKey: string;
  descKey: string;
  accent: string;
}

const FEATURES: Feature[] = [
  { icon: <Brain size={28} />, titleKey: "home_feat_triage_title", descKey: "home_feat_triage_desc", accent: "from-teal-400 to-emerald-400" },
  { icon: <ShieldAlert size={28} />, titleKey: "home_feat_passport_title", descKey: "home_feat_passport_desc", accent: "from-red-400 to-orange-400" },
  { icon: <Users size={28} />, titleKey: "home_feat_family_title", descKey: "home_feat_family_desc", accent: "from-indigo-400 to-purple-400" },
  { icon: <Video size={28} />, titleKey: "home_feat_doctor_title", descKey: "home_feat_doctor_desc", accent: "from-sky-400 to-indigo-400" },
  { icon: <ShieldAlert size={28} />, titleKey: "home_feat_sos_title", descKey: "home_feat_sos_desc", accent: "from-rose-500 to-red-500" },
  { icon: <MessageSquareText size={28} />, titleKey: "home_feat_sms_title", descKey: "home_feat_sms_desc", accent: "from-amber-400 to-orange-400" },
  { icon: <Globe size={28} />, titleKey: "home_feat_lang_title", descKey: "home_feat_lang_desc", accent: "from-teal-400 to-sky-400" },
  { icon: <Sparkles size={28} />, titleKey: "home_feat_free_title", descKey: "home_feat_free_desc", accent: "from-violet-400 to-fuchsia-400" },
];

function FeatureCarousel() {
  const { t } = useLocale();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [direction, setDirection] = useState(1);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => {
      setDirection(1);
      setIndex((i) => (i + 1) % FEATURES.length);
    }, 4500);
    return () => clearInterval(id);
  }, [paused]);

  const go = (delta: number) => {
    setDirection(delta);
    setIndex((i) => (i + delta + FEATURES.length) % FEATURES.length);
  };

  const feature = FEATURES[index];

  return (
    <div
      className="w-full max-w-2xl mx-auto"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="relative glass-panel p-8 md:p-10 min-h-[280px] flex items-center overflow-hidden">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={index}
            custom={direction}
            initial={{ opacity: 0, x: 40 * direction }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -40 * direction }}
            transition={{ duration: 0.4, ease: "easeInOut" }}
            className="w-full flex flex-col md:flex-row items-center gap-6 text-center md:text-left"
          >
            <div className={`shrink-0 w-16 h-16 rounded-2xl bg-gradient-to-br ${feature.accent} flex items-center justify-center text-white shadow-lg`}>
              {feature.icon}
            </div>
            <div>
              <h3 className="text-xl md:text-2xl font-bold mb-2 text-[var(--foreground)]">{t(feature.titleKey)}</h3>
              <p className="text-gray-500 dark:text-gray-400">{t(feature.descKey)}</p>
            </div>
          </motion.div>
        </AnimatePresence>

        <button
          type="button"
          onClick={() => go(-1)}
          aria-label={t('home_carousel_prev')}
          className="hidden sm:flex absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/40 dark:bg-black/30 backdrop-blur-md border border-white/20 items-center justify-center hover:bg-white/60 dark:hover:bg-black/50 transition-colors"
        >
          <ChevronLeft size={18} />
        </button>
        <button
          type="button"
          onClick={() => go(1)}
          aria-label={t('home_carousel_next')}
          className="hidden sm:flex absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/40 dark:bg-black/30 backdrop-blur-md border border-white/20 items-center justify-center hover:bg-white/60 dark:hover:bg-black/50 transition-colors"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      <div className="flex items-center justify-center gap-2 mt-5">
        {FEATURES.map((f, i) => (
          <button
            key={f.titleKey}
            type="button"
            onClick={() => { setDirection(i > index ? 1 : -1); setIndex(i); }}
            aria-label={t(f.titleKey)}
            className={`h-2 rounded-full transition-all ${i === index ? "w-6 bg-teal-400" : "w-2 bg-gray-400/40"}`}
          />
        ))}
      </div>
    </div>
  );
}

/** Small icon+label pills that drift gently around the hero — desktop only
 * to avoid crowding a phone-width viewport. Purely decorative branding, no
 * live data behind them. */
function FloatingBadges({ live }: { live: boolean }) {
  const { t } = useLocale();
  const badges = [
    { key: "home_badge_secure", cls: "top-4 left-[6%]", duration: 6 },
    { key: "home_badge_offline", cls: "top-24 right-[4%]", duration: 7 },
    { key: "home_badge_bilingual", cls: "bottom-10 left-[10%]", duration: 5.5 },
    { key: "home_badge_triage", cls: "bottom-28 right-[8%]", duration: 6.5 },
  ];
  return (
    <div className="hidden lg:block absolute inset-0 -z-10 pointer-events-none">
      {badges.map((b, i) => (
        <motion.div
          key={b.key}
          animate={{ y: [0, -14, 0] }}
          transition={{ duration: b.duration, repeat: Infinity, ease: "easeInOut", delay: i * 0.4 }}
          className={`absolute ${b.cls} px-3 py-1.5 rounded-full glass-panel text-xs font-bold text-gray-600 dark:text-gray-300 whitespace-nowrap`}
        >
          {t(b.key)}
        </motion.div>
      ))}
      {live && (
        <motion.div
          animate={{ y: [0, -10, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[45%] right-[2%] px-3 py-1.5 rounded-full glass-panel text-xs font-bold text-green-500 whitespace-nowrap flex items-center gap-1.5"
        >
          <Radio size={12} className="animate-pulse" /> {t('home_live')}
        </motion.div>
      )}
    </div>
  );
}

export default function Home() {
  const { user } = useAuth();
  const { t } = useLocale();
  const [socketConnected, setSocketConnected] = useState(false);

  useEffect(() => {
    const socket = io(WS_URL);
    socket.on("connect", () => setSocketConnected(true));
    socket.on("disconnect", () => setSocketConnected(false));
    return () => { socket.disconnect(); };
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center p-6 lg:p-16 relative overflow-hidden">
      {/* Background blobs for the glassmorphism effect */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-20 pointer-events-none">
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

      <div className="relative w-full max-w-4xl">
        <FloatingBadges live={socketConnected} />

        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-10 pt-8"
        >
          <h1 className="text-5xl font-extrabold tracking-tight lg:text-7xl mb-4 text-[var(--foreground)]">
            GramCare <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-teal-400">AI</span>
          </h1>
          <p className="text-xl text-gray-500 dark:text-gray-400 max-w-2xl mx-auto">
            {t('home_tagline')}
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-8">
            <Link
              href={user ? "/book" : "/login"}
              className="neu-button px-6 py-3 bg-gradient-to-r from-indigo-500 to-teal-400 text-white font-bold rounded-xl flex items-center justify-center gap-2 w-full sm:w-auto"
            >
              {user ? t('home_hero_cta_primary_user') : t('home_hero_cta_primary_guest')}
              <ArrowRight size={18} />
            </Link>
            <Link
              href="/symptom-checker"
              className="neu-button px-6 py-3 font-bold rounded-xl flex items-center justify-center gap-2 w-full sm:w-auto"
            >
              <Brain size={18} className="text-teal-500" />
              {t('home_hero_cta_secondary')}
            </Link>
          </div>
        </motion.div>
      </div>

      {/* Feature showcase */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-4xl mt-8 text-center"
      >
        <p className="text-sm font-bold uppercase tracking-wider text-teal-500 mb-2">{t('home_features_eyebrow')}</p>
        <h2 className="text-3xl lg:text-4xl font-extrabold mb-3 text-[var(--foreground)]">{t('home_features_heading')}</h2>
        <p className="text-gray-500 dark:text-gray-400 max-w-2xl mx-auto mb-10">{t('home_features_subheading')}</p>

        <FeatureCarousel />
      </motion.div>

      {/* Mission strip */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.6 }}
        className="w-full max-w-3xl mt-20 mb-8"
      >
        <div className="neu-panel p-8 md:p-10 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-teal-400/5 pointer-events-none" />
          <h3 className="text-xl font-bold mb-3 text-[var(--foreground)]">{t('home_mission_heading')}</h3>
          <p className="text-gray-500 dark:text-gray-400 max-w-xl mx-auto">{t('home_mission_body')}</p>
        </div>
      </motion.div>
    </div>
  );
}
