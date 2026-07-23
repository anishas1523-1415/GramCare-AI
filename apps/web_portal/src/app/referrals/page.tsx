"use client";

// Patient-facing view of the Referral Network (modules/referrals/router.py):
// a doctor treating this patient may hand them off to a specific colleague
// or open a referral to any doctor of a target specialty. This page gives
// the patient visibility into every referral made about them and its
// current status, mirroring the transparency lab-tests/page.tsx already
// gives for lab bookings.

import { motion } from "framer-motion";
import { Share2, Stethoscope, ArrowRightCircle, Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import ThemedLoader from "../../components/ThemedLoader";
import api from "../../lib/api";
import type { Referral } from "../../types";

const STATUS_STYLE: Record<Referral["status"], string> = {
  PENDING: "bg-amber-500/15 text-amber-500 border-amber-500/30",
  ACCEPTED: "bg-teal-500/15 text-teal-500 border-teal-500/30",
  DECLINED: "bg-red-500/15 text-red-500 border-red-500/30",
  COMPLETED: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
};

const STATUS_LABEL: Record<Referral["status"], string> = {
  PENDING: "Pending",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  COMPLETED: "Completed",
};

export default function ReferralsPage() {
  const { user } = useAuth();
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const res = await api.get<Referral[]>("/referrals/mine");
        setReferrals(res.data);
      } catch {
        setError("Could not load your referrals.");
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to see your referrals.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 lg:p-16 flex items-start justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-3xl w-full p-8 relative overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-teal-400/5 z-0" />
        <div className="relative z-10">
          <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
            <Share2 className="text-indigo-500" /> Referrals
          </h1>
          <p className="text-gray-500 mb-8">
            Specialist referrals made about you by your doctors, and their current status.
          </p>

          {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

          {loading ? (
            <ThemedLoader variant="doctor" label="Loading your referrals…" />
          ) : referrals.length === 0 ? (
            <p className="text-center text-gray-400 py-12">No referrals have been made about you yet.</p>
          ) : (
            <div className="space-y-4">
              {referrals.map((r) => (
                <div key={r.id} className="neu-panel p-4">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <p className="font-bold flex items-center gap-1.5">
                        <Stethoscope size={15} className="text-indigo-500" /> {r.specialty}
                      </p>
                      <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">{r.reason}</p>
                    </div>
                    <span className={`shrink-0 px-2.5 py-1 rounded-full text-xs font-bold border ${STATUS_STYLE[r.status]}`}>
                      {STATUS_LABEL[r.status]}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-400 mt-2">
                    <span className="flex items-center gap-1">
                      <ArrowRightCircle size={12} />
                      {r.referred_to_doctor_id
                        ? `Referred to Doctor #${r.referred_to_doctor_id}`
                        : `Open referral — awaiting a ${r.specialty} doctor`}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock size={12} /> {new Date(r.created_at).toLocaleString()}
                    </span>
                  </div>
                  {r.notes && (
                    <p className="text-xs text-gray-500 mt-2 pt-2 border-t border-white/10">{r.notes}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
