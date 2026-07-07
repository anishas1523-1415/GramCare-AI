"use client";

// Report entry — submits POST /lab/bookings/{id}/report, which (server-side)
// auto-syncs the structured result into the patient's Family Health Wallet
// and pushes them an FCM notification. This screen exists to make that
// cross-module integration visible to lab staff, not just silently succeed.

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Plus, Trash2, CheckCircle2, FlaskConical } from 'lucide-react';
import api from '../../../lib/api';
import type { LabResultValue } from '../../../types';

const FLAGS = ['NORMAL', 'LOW', 'HIGH'] as const;

const emptyRow = (): LabResultValue => ({ parameter: '', value: '', unit: '', reference_range: '', flag: 'NORMAL' });

export default function ReportEntryPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const bookingId = params.id;
  const testName = search.get('test') || 'this test';
  const patientId = search.get('patient');

  const [rows, setRows] = useState<LabResultValue[]>([emptyRow()]);
  const [summary, setSummary] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const updateRow = (idx: number, field: keyof LabResultValue, value: string) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  };

  const addRow = () => setRows((prev) => [...prev, emptyRow()]);
  const removeRow = (idx: number) => setRows((prev) => prev.filter((_, i) => i !== idx));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const values = rows.filter((r) => r.parameter.trim() && r.value.trim());
      await api.post(`/lab/bookings/${bookingId}/report`, {
        values,
        summary: summary || undefined,
      });
      setDone(true);
    } catch {
      setError('Could not submit the report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-panel p-10 max-w-md text-center"
        >
          <CheckCircle2 size={56} className="text-emerald-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">Report Submitted</h2>
          <p className="text-gray-500 mb-6">
            The {testName} result has synced automatically into the patient&apos;s
            Family Health Wallet, and they&apos;ve been notified.
          </p>
          <button
            onClick={() => router.push('/dashboard')}
            className="neu-button w-full py-3 bg-[var(--primary)] text-white font-bold rounded-xl"
          >
            Back to Queue
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6 lg:p-10">
      <header className="mb-6">
        <h1 className="text-2xl font-extrabold flex items-center gap-3">
          <FlaskConical className="text-[var(--primary)]" size={28} /> Enter Report — {testName}
        </h1>
        {patientId && <p className="text-gray-500 text-sm mt-1">Patient #{patientId} · Booking #{bookingId}</p>}
      </header>

      <form onSubmit={handleSubmit} className="glass-panel p-6 space-y-5">
        <div className="space-y-3">
          {rows.map((row, idx) => (
            <div key={idx} className="grid grid-cols-12 gap-2 items-center">
              <input
                aria-label={`Result parameter ${idx + 1}`}
                placeholder="Parameter (e.g. Hemoglobin)"
                value={row.parameter}
                onChange={(e) => updateRow(idx, 'parameter', e.target.value)}
                className="col-span-4 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              />
              <input
                aria-label={`Result value ${idx + 1}`}
                placeholder="Value"
                value={row.value}
                onChange={(e) => updateRow(idx, 'value', e.target.value)}
                className="col-span-2 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              />
              <input
                aria-label={`Result unit ${idx + 1}`}
                placeholder="Unit"
                value={row.unit ?? ''}
                onChange={(e) => updateRow(idx, 'unit', e.target.value)}
                className="col-span-2 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              />
              <input
                aria-label={`Reference range ${idx + 1}`}
                placeholder="Reference range"
                value={row.reference_range ?? ''}
                onChange={(e) => updateRow(idx, 'reference_range', e.target.value)}
                className="col-span-2 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              />
              <select
                aria-label={`Result flag ${idx + 1}`}
                value={row.flag ?? 'NORMAL'}
                onChange={(e) => updateRow(idx, 'flag', e.target.value)}
                className="col-span-1 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              >
                {FLAGS.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
              <button
                type="button"
                onClick={() => removeRow(idx)}
                disabled={rows.length === 1}
                aria-label={`Remove result row ${idx + 1}`}
                className="col-span-1 text-red-500 disabled:opacity-30 flex justify-center"
              >
                <Trash2 size={18} />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addRow}
            className="text-sm font-semibold text-[var(--primary)] flex items-center gap-1"
          >
            <Plus size={16} /> Add parameter
          </button>
        </div>

        <div>
          <label className="block text-sm font-semibold mb-2">Summary (optional)</label>
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={3}
            placeholder="e.g. All values within normal range."
            className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
          />
        </div>

        {error && <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="neu-button w-full py-3 bg-[var(--primary)] text-white font-bold rounded-xl disabled:opacity-50"
        >
          {submitting ? 'Submitting…' : 'Submit Report'}
        </button>
      </form>
    </div>
  );
}
