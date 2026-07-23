"use client";

// AI Care Navigator — a patient-facing "what should I do next?" digest.
// The backend (modules/navigator/router.py, GET /navigator/next-steps)
// aggregates several signals (active SOS, ready lab reports, upcoming
// confirmed appointments, unfulfilled prescriptions, and — where available
// — preventive-care reminders) into one ranked list, each item carrying its
// own explainability `reason` and a suggested `cta`. A dedicated page (vs.
// bolting this onto /family) keeps the widget from disrupting an existing
// page's layout and gives patients a single, bookmarkable "start here" view.

import { motion } from "framer-motion";
import {
  Compass, ShieldAlert, FlaskConical, CalendarClock, Pill, Sparkles,
  CheckCircle2, ChevronRight,
} from "lucide-react";
import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import Link from "next/link";
import { useAuth } from "../../contexts/AuthContext";
import ThemedLoader from "../../components/ThemedLoader";
import api from "../../lib/api";
import type { NavigatorItem } from "../../types";

const PRIORITY_STYLE: Record<NavigatorItem["priority"], string> = {
  CRITICAL: "border-red-500 bg-red-500/10 text-red-500",
  HIGH: "border-orange-500 bg-orange-500/10 text-orange-500",
  MEDIUM: "border-amber-500 bg-amber-500/10 text-amber-500",
  LOW: "border-gray-400 bg-gray-400/10 text-gray-500",
};

const CATEGORY_ICON: Record<string, ComponentType<{ size?: number; className?: string }>> = {
  sos: ShieldAlert,
  lab: FlaskConical,
  appointment: CalendarClock,
  prescription: Pill,
  preventive: Sparkles,
  all_clear: CheckCircle2,
};

export default function MyCarePage() {
  const { user } = useAuth();
  const [items, setItems] = useState<NavigatorItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get<NavigatorItem[]>("/navigator/next-steps")
      .then((res) => {
        if (!cancelled) setItems(res.data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load your next steps. Please try again.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to see your next steps.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 lg:p-16 flex items-start justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-2xl w-full p-8 relative overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-teal-400/5 to-indigo-500/5 z-0" />
        <div className="relative z-10">
          <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
            <Compass className="text-teal-500" /> My Care
          </h1>
          <p className="text-gray-500 mb-6">
            Everything that needs your attention right now, ranked by urgency.
          </p>

          {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

          {loading ? (
            <ThemedLoader variant="wallet" label="Checking on your care…" />
          ) : (
            <div className="space-y-3">
              {items.map((item, i) => {
                const Icon = CATEGORY_ICON[item.category] || Sparkles;
                const style = PRIORITY_STYLE[item.priority];
                const body = (
                  <div
                    className={`neu-panel p-4 border-l-4 flex items-start gap-3 ${style.split(" ")[0]}`}
                  >
                    <div className={`shrink-0 p-2 rounded-lg ${style}`}>
                      <Icon size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="font-bold truncate">{item.title}</p>
                        <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold border ${style}`}>
                          {item.priority}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500">{item.reason}</p>
                    </div>
                    {item.cta_label && item.cta_route && (
                      <ChevronRight size={18} className="text-gray-400 shrink-0 mt-2" />
                    )}
                  </div>
                );

                return (
                  <motion.div
                    key={`${item.category}-${i}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    {item.cta_label && item.cta_route ? (
                      <Link href={item.cta_route} className="block hover:ring-2 hover:ring-teal-400/50 rounded-2xl transition-shadow">
                        {body}
                      </Link>
                    ) : (
                      body
                    )}
                    {item.cta_label && item.cta_route && (
                      <p className="text-xs font-bold text-teal-500 mt-1 ml-1">{item.cta_label} →</p>
                    )}
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
