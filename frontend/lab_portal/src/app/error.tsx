"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("GramCare Lab Portal — unhandled page error:", error);
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
          This page hit an unexpected error. Your booking and report data is safe — try again.
        </p>
        <div className="flex gap-3">
          <button
            onClick={reset}
            className="neu-button flex-1 py-3 bg-[var(--primary)] text-white font-bold rounded-xl flex items-center justify-center gap-2"
          >
            <RotateCcw size={16} /> Try again
          </button>
          <a
            href="/dashboard"
            className="flex-1 py-3 rounded-xl border border-white/30 font-bold flex items-center justify-center gap-2"
          >
            <Home size={16} /> Dashboard
          </a>
        </div>
      </motion.div>
    </div>
  );
}
