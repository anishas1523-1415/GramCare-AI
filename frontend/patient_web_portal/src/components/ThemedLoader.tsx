"use client";

// Per-module themed loading animations (planning doc: "ஒவ்வொரு ஃபீச்சருக்கும்
// ஒரு தீம், ட்ரான்சிஷன், அனிமேஷன் எல்லாம் பண்ணனும்" — every module needs its
// own visual identity, including its loading state, not a single generic
// spinner reused everywhere).

import React from 'react';
import { motion } from 'framer-motion';

export type LoaderVariant = 'symptom' | 'pharmacy' | 'doctor' | 'emergency' | 'lab' | 'wallet' | 'analytics';

const THEME: Record<LoaderVariant, { color: string; label: string }> = {
  symptom: { color: '#2DD4BF', label: 'Analyzing symptoms…' },
  pharmacy: { color: '#10B981', label: 'Checking pharmacy stock…' },
  doctor: { color: '#4F46E5', label: 'Loading consultation…' },
  emergency: { color: '#EF4444', label: 'Connecting to emergency services…' },
  lab: { color: '#7C3AED', label: 'Loading lab data…' },
  wallet: { color: '#F59E0B', label: 'Loading health records…' },
  analytics: { color: '#9333EA', label: 'Crunching community health data…' },
};

function SymptomScan({ color }: { color: string }) {
  // A sweeping scan-line over a body/pulse silhouette — "medical scanning".
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
      <circle cx="36" cy="36" r="30" stroke={color} strokeWidth="2" opacity="0.2" />
      <motion.circle
        cx="36" cy="36" r="30" stroke={color} strokeWidth="2" strokeDasharray="8 10"
        animate={{ rotate: 360 }} transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        style={{ transformOrigin: '36px 36px' }}
      />
      <motion.path
        d="M14 36 h10 l4 -14 l6 28 l6 -20 l4 6 h14"
        stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }}
        transition={{ duration: 1.4, repeat: Infinity, repeatType: 'loop', ease: 'easeInOut' }}
      />
    </svg>
  );
}

function PharmacyPill({ color }: { color: string }) {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
      {[0, 1, 2].map((i) => (
        <motion.rect
          key={i}
          x={16 + i * 16} y="30" width="10" height="20" rx="5"
          fill={color} opacity={0.25 + i * 0.1}
          animate={{ y: [30, 20, 30] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }}
        />
      ))}
    </svg>
  );
}

function DoctorPulse({ color }: { color: string }) {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
      <motion.circle
        cx="36" cy="36" r="14" fill="none" stroke={color} strokeWidth="3"
        animate={{ scale: [1, 1.6], opacity: [0.6, 0] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
        style={{ transformOrigin: '36px 36px' }}
      />
      <circle cx="36" cy="36" r="10" fill={color} />
    </svg>
  );
}

function EmergencyEcg({ color }: { color: string }) {
  // ECG heartbeat trace.
  return (
    <svg width="96" height="48" viewBox="0 0 96 48" fill="none">
      <motion.path
        d="M0 24 H24 L30 10 L38 40 L44 24 L50 24 L56 4 L62 24 H96"
        stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none"
        initial={{ pathLength: 0, opacity: 0.4 }}
        animate={{ pathLength: [0, 1], opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
      />
    </svg>
  );
}

function LabMicroscope({ color }: { color: string }) {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
      <motion.circle
        cx="36" cy="30" r="14" stroke={color} strokeWidth="2.5" fill="none"
        animate={{ scale: [1, 1.15, 1] }}
        transition={{ duration: 1.3, repeat: Infinity, ease: 'easeInOut' }}
      />
      {[0, 1, 2].map((i) => (
        <motion.circle
          key={i} cx={36 + Math.cos((i * 2 * Math.PI) / 3) * 6} cy={30 + Math.sin((i * 2 * Math.PI) / 3) * 6} r="2"
          fill={color}
          animate={{ opacity: [0.2, 1, 0.2] }}
          transition={{ duration: 1.3, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
      <path d="M30 42 L20 60 H52 L42 42" stroke={color} strokeWidth="2" fill="none" strokeLinejoin="round" />
    </svg>
  );
}

function WalletFolder({ color }: { color: string }) {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
      <rect x="14" y="24" width="44" height="32" rx="4" stroke={color} strokeWidth="2.5" fill="none" />
      <path d="M14 28 V22 a3 3 0 0 1 3 -3 h12 l6 6 h20 a3 3 0 0 1 3 3 v0" stroke={color} strokeWidth="2.5" fill="none" />
      {[0, 1, 2].map((i) => (
        <motion.rect
          key={i} x="20" y={33 + i * 6} width="32" height="3" rx="1.5" fill={color}
          animate={{ opacity: [0.2, 0.9, 0.2] }}
          transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.25 }}
        />
      ))}
    </svg>
  );
}

function AnalyticsBars({ color }: { color: string }) {
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
      {[0, 1, 2, 3].map((i) => (
        <motion.rect
          key={i} x={12 + i * 14} width="9" rx="2" fill={color}
          initial={{ height: 8, y: 54 }}
          animate={{ height: [8, 34, 14, 44, 8], y: [54, 28, 48, 18, 54] }}
          transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.15, ease: 'easeInOut' }}
        />
      ))}
    </svg>
  );
}

const ICONS: Record<LoaderVariant, React.FC<{ color: string }>> = {
  symptom: SymptomScan,
  pharmacy: PharmacyPill,
  doctor: DoctorPulse,
  emergency: EmergencyEcg,
  lab: LabMicroscope,
  wallet: WalletFolder,
  analytics: AnalyticsBars,
};

export default function ThemedLoader({
  variant,
  label,
  className = '',
}: {
  variant: LoaderVariant;
  label?: string;
  className?: string;
}) {
  const { color, label: defaultLabel } = THEME[variant];
  const Icon = ICONS[variant];
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-10 ${className}`}>
      <Icon color={color} />
      <p className="text-sm font-semibold" style={{ color }}>{label ?? defaultLabel}</p>
    </div>
  );
}
