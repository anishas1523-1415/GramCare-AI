"use client";

// Community Health Intelligence — the planning doc's outbreak-cluster view
// for health authorities: anonymized clusters of similar AI-assessed
// conditions inside a time window, with alert flags on clusters that cross
// the outbreak threshold.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, AlertTriangle, Activity, Building2, Pill } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import api from '../../../lib/api';

interface Cluster {
  condition: string;
  case_count: number;
  avg_severity: number;
  max_severity: number;
  first_seen: string;
  last_seen: string;
  alert: boolean;
}

interface Overview {
  window_days: number;
  total_assessments: number;
  critical_assessments: number;
  active_sos: number;
  unfulfilled_prescriptions: number;
  registered_pharmacies: number;
}

export default function HealthIntelligence() {
  const { user, loading: authLoading } = useAuth();
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [days, setDays] = useState(7);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !user) return;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const [c, o] = await Promise.all([
          api.get<Cluster[]>(`/analytics/health-clusters?days=${days}&min_cases=3`),
          api.get<Overview>(`/analytics/overview?days=${days}`),
        ]);
        setClusters(c.data);
        setOverview(o.data);
      } catch {
        setError('Not authorized or data unavailable (health-authority roles only).');
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, days]);

  const maxCount = Math.max(1, ...clusters.map((c) => c.case_count));

  return (
    <div className="min-h-screen p-8 lg:p-16 max-w-5xl mx-auto">
      <h1 className="text-4xl font-extrabold flex items-center gap-3 mb-2">
        <BarChart3 className="text-purple-500" size={40} /> Community Health Intelligence
      </h1>
      <p className="text-gray-500 mb-8">
        Anonymized symptom clusters across the region — early warning for disease spread.
      </p>

      <div className="flex gap-2 mb-8">
        {[7, 14, 30].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-4 py-2 rounded-xl font-semibold text-sm ${days === d ? 'bg-purple-500 text-white' : 'bg-white/50 dark:bg-black/30'}`}
          >
            Last {d} days
          </button>
        ))}
      </div>

      {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

      {loading ? (
        <div className="flex justify-center p-10"><div className="animate-spin w-10 h-10 border-4 border-purple-500 border-t-transparent rounded-full" /></div>
      ) : (
        <>
          {overview && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
              {[
                { icon: Activity, label: 'AI assessments', value: overview.total_assessments, color: 'text-teal-500' },
                { icon: AlertTriangle, label: 'Critical cases', value: overview.critical_assessments, color: 'text-red-500' },
                { icon: Building2, label: 'Active SOS', value: overview.active_sos, color: 'text-orange-500' },
                { icon: Pill, label: 'Pending prescriptions', value: overview.unfulfilled_prescriptions, color: 'text-indigo-500' },
              ].map(({ icon: Icon, label, value, color }) => (
                <div key={label} className="glass-panel p-4 text-center">
                  <Icon className={`mx-auto mb-2 ${color}`} size={24} />
                  <div className="text-3xl font-extrabold">{value}</div>
                  <div className="text-xs text-gray-500">{label}</div>
                </div>
              ))}
            </div>
          )}

          <h2 className="text-xl font-bold mb-4">Condition clusters</h2>
          {clusters.length === 0 ? (
            <div className="glass-panel p-10 text-center text-gray-500">
              No symptom clusters in this window.
            </div>
          ) : (
            <div className="space-y-3">
              {clusters.map((c) => (
                <motion.div
                  key={c.condition}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`glass-panel p-4 ${c.alert ? 'border-l-8 border-l-red-500' : ''}`}
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold capitalize">{c.condition}</span>
                    <span className="text-sm text-gray-500">
                      {c.case_count} case{c.case_count === 1 ? '' : 's'} · avg severity {c.avg_severity}
                      {c.alert && <span className="ml-2 px-2 py-0.5 bg-red-500 text-white rounded text-xs font-bold animate-pulse">CLUSTER ALERT</span>}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden">
                    <div
                      className={`h-full ${c.alert ? 'bg-red-500' : 'bg-purple-400'}`}
                      style={{ width: `${(c.case_count / maxCount) * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(c.first_seen).toLocaleDateString()} → {new Date(c.last_seen).toLocaleDateString()}
                  </p>
                </motion.div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
