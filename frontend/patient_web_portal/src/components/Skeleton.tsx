"use client";

// Skeleton loading (planning doc UI/UX requirement) — shimmering content
// placeholders instead of a spin-and-wait blank screen, used on the
// highest-traffic loading states (doctor queue, patient search results).

import React from 'react';
import { motion } from 'framer-motion';

function ShimmerBlock({ className = '' }: { className?: string }) {
  return (
    <motion.div
      className={`rounded-lg bg-gradient-to-r from-white/10 via-white/30 to-white/10 dark:from-black/10 dark:via-white/10 dark:to-black/10 bg-[length:200%_100%] ${className}`}
      animate={{ backgroundPosition: ['200% 0', '-200% 0'] }}
      transition={{ duration: 1.6, repeat: Infinity, ease: 'linear' }}
    />
  );
}

/** A single card-shaped skeleton row — mirrors the shape of a patient
 * queue item / search result card used across the app's glass-panel style. */
export function SkeletonCard() {
  return (
    <div className="glass-panel p-4 flex items-center justify-between gap-4">
      <div className="flex-1 space-y-2">
        <ShimmerBlock className="h-4 w-1/3" />
        <ShimmerBlock className="h-3 w-2/3" />
      </div>
      <ShimmerBlock className="h-9 w-24 shrink-0" />
    </div>
  );
}

export function SkeletonList({ count = 4 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
