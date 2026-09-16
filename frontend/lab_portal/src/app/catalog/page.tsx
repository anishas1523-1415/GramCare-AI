"use client";

// Quick-reference test catalog so front-desk staff can tell a walk-in
// patient the prep instructions (fasting hours, etc.) without hunting
// through paperwork. Read-only, search-only.

import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, BookOpen, Clock, Droplet } from 'lucide-react';
import api from '../../lib/api';
import type { LabTestInfo } from '../../types';
import { useLocale } from '../../contexts/LocaleContext';

export default function CatalogPage() {
  const { t } = useLocale();
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
          <BookOpen className="text-[var(--primary)]" size={28} /> {t('test_catalog')}
        </h1>
        <p className="text-gray-500 text-sm mt-1">{t('catalog_blurb')}</p>
      </header>

      <div className="relative mb-6">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('search_tests_placeholder')}
          className="w-full pl-11 p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
        />
      </div>

      {loading ? (
        <p className="text-gray-500 text-center py-10">{t('searching')}</p>
      ) : tests.length === 0 ? (
        <p className="text-gray-500 text-center py-10">{t('no_matching_tests')}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tests.map((test) => (
            <motion.div
              key={test.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-panel p-5"
            >
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-bold text-lg">{test.name}</h3>
                <span className="text-xs font-bold px-2 py-1 rounded-full bg-[var(--primary)]/15 text-[var(--primary)]">
                  {test.category}
                </span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-300 mb-3">{test.prep_instructions}</p>
              <div className="flex gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1"><Clock size={13} /> {test.typical_turnaround_hours}{t('turnaround_suffix')}</span>
                <span className="flex items-center gap-1"><Droplet size={13} /> {test.sample_type}</span>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
