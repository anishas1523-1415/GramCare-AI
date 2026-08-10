"use client";

// Route-level error boundary (Next.js App Router convention). Without this,
// an unhandled render/runtime error in any page previously fell through to
// Next.js's bare default error screen — a jarring dead end in a healthcare
// app where the user may be mid-triage or mid-booking.

import { useEffect } from "react";
import { motion } from "framer-motion";
import Link from "next/link";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("GramCare AI — unhandled page error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-md w-full p-8 text-center"
      >
        <AlertTriangle className="mx-auto mb-4 text-red-500" size={48} />
        <h1 className="text-xl font-bold mb-2">Something went wrong</h1>
        <p className="text-gray-500 text-sm mb-6">
          This page hit an unexpected error. Your data is safe — try again, or head back home.
          If this keeps happening, please contact support.
        </p>
        <div className="flex gap-3">
          <button
            onClick={reset}
            className="neu-button flex-1 py-3 bg-indigo-500 text-white font-bold rounded-xl flex items-center justify-center gap-2"
          >
            <RotateCcw size={16} /> Try again
          </button>
          <Link
            href="/"
            className="flex-1 py-3 rounded-xl border border-white/30 font-bold flex items-center justify-center gap-2"
          >
            <Home size={16} /> Home
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
