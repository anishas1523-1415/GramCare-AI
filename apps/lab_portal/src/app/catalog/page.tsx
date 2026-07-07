"use client";

// Quick-reference test catalog so front-desk staff can tell a walk-in
// patient the prep instructions (fasting hours, etc.) without hunting
// through paperwork. Read-only, search-only.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, BookOpen, Clock, Droplet } from 'lucide-react';
import api from '../../lib/api';
import type { LabTestInfo } from '../../types';

export default function CatalogPage() {
  const [query, setQuery] = useState('');
  const [tests, setTests] = useState<LabTestInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.get<LabTestInfo[]>('/lab/tests', { params: query ? { query } : {} });
        setTests(res.data);
      } catch {
        setTests([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [query]);

  return (
    <div className="max-w-4xl mx-auto p-6 lg:p-10">
      <header className="mb-6">
        <h1 className="text-2xl font-extrabold flex items-center gap-3">
          <BookOpen className="text-[var(--primary)]" size={28} /> Test Catalog
        </h1>
        <p className="text-gray-500 text-sm mt-1">Look up prep instructions for any test.</p>
      </header>

      <div className="relative mb-6">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by test name or category…"
          className="w-full pl-11 p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
        />
      </div>

      {loading ? (
        <p className="text-gray-500 text-center py-10">Searching…</p>
      ) : tests.length === 0 ? (
        <p className="text-gray-500 text-center py-10">No matching tests.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tests.map((t) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-panel p-5"
            >
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-bold text-lg">{t.name}</h3>
                <span className="text-xs font-bold px-2 py-1 rounded-full bg-[var(--primary)]/15 text-[var(--primary)]">
                  {t.category}
                </span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">{t.prep_instructions}</p>
              <div className="flex gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1"><Clock size={13} /> {t.typical_turnaround_hours}h turnaround</span>
                <span className="flex items-center gap-1"><Droplet size={13} /> {t.sample_type}</span>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
