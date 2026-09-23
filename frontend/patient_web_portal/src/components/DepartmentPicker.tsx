"use client";

// Departments a hospital runs, as pickable chips plus free text.
//
// This was one comma-separated text box, which put the burden of spelling
// and separators on the person filling it in and produced values nothing
// else could match on reliably ("Ortho", "orthopedics", "Orthopaedics").
// The list below is the standard set an Indian district hospital would
// recognise; anything not on it can still be typed, because a list can
// never cover every speciality.

import React from 'react';
import { Check, Plus, X } from 'lucide-react';

/** Grouped so a long list stays scannable rather than being one wall of chips. */
export const DEPARTMENT_GROUPS: Record<string, string[]> = {
  'Emergency & critical care': [
    'Emergency / Casualty',
    'Intensive Care (ICU)',
    'Trauma Care',
    'Ambulance Service',
    'Blood Bank',
  ],
  'Core medical': [
    'General Medicine',
    'General Surgery',
    'Paediatrics',
    'Obstetrics & Gynaecology',
    'Orthopaedics',
    'Dermatology',
    'Psychiatry',
    'Dentistry',
    'Ophthalmology',
    'ENT',
  ],
  Specialist: [
    'Cardiology',
    'Neurology',
    'Nephrology',
    'Urology',
    'Gastroenterology',
    'Pulmonology',
    'Endocrinology',
    'Oncology',
    'Rheumatology',
    'Plastic Surgery',
  ],
  Diagnostics: [
    'Radiology / X-Ray',
    'Ultrasound',
    'CT Scan',
    'MRI',
    'Pathology Lab',
    'ECG / Echo',
  ],
  'Public health': [
    'Immunisation',
    'Maternal & Child Health',
    'Tuberculosis (DOTS)',
    'Dialysis',
    'Physiotherapy',
    'Pharmacy',
  ],
};

interface Props {
  /** Comma-separated, which is how the API stores it. */
  value: string;
  onChange: (value: string) => void;
  label?: string;
}

function parse(value: string): string[] {
  return value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}

export default function DepartmentPicker({ value, onChange, label }: Props) {
  const selected = React.useMemo(() => parse(value), [value]);
  const [custom, setCustom] = React.useState('');

  const commit = (next: string[]) => {
    // De-duplicated case-insensitively, so "ENT" and "ent" cannot both land
    // in the list and split the same department in two.
    const seen = new Set<string>();
    const unique = next.filter((d) => {
      const k = d.toLowerCase();
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
    onChange(unique.join(', '));
  };

  const toggle = (dept: string) => {
    const has = selected.some((d) => d.toLowerCase() === dept.toLowerCase());
    commit(has ? selected.filter((d) => d.toLowerCase() !== dept.toLowerCase()) : [...selected, dept]);
  };

  const addCustom = () => {
    const v = custom.trim();
    if (!v) return;
    commit([...selected, v]);
    setCustom('');
  };

  return (
    <div className="space-y-3">
      {label && <label className="block text-sm font-semibold">{label}</label>}

      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map((d) => (
            <span
              key={d}
              className="inline-flex items-center gap-1 rounded-full bg-indigo-500/15 text-indigo-600 dark:text-indigo-300 px-2.5 py-1 text-xs font-semibold"
            >
              {d}
              <button
                type="button"
                onClick={() => toggle(d)}
                aria-label={`Remove ${d}`}
                className="hover:opacity-70"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-white/20 divide-y divide-white/10 max-h-64 overflow-auto">
        {Object.entries(DEPARTMENT_GROUPS).map(([group, depts]) => (
          <div key={group} className="p-2.5">
            <p className="text-[11px] uppercase tracking-wide text-gray-500 font-bold mb-1.5">{group}</p>
            <div className="flex flex-wrap gap-1.5">
              {depts.map((d) => {
                const on = selected.some((s) => s.toLowerCase() === d.toLowerCase());
                return (
                  <button
                    key={d}
                    type="button"
                    onClick={() => toggle(d)}
                    aria-pressed={on}
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium border transition-colors ${
                      on
                        ? 'bg-indigo-500 text-white border-indigo-500'
                        : 'border-white/25 hover:bg-indigo-500/10'
                    }`}
                  >
                    {on && <Check size={11} />}
                    {d}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              // Inside a form, Enter would otherwise submit the whole page.
              e.preventDefault();
              addCustom();
            }
          }}
          placeholder="Add another department…"
          className="flex-1 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm focus:ring-2 focus:ring-indigo-400 focus:outline-none"
        />
        <button
          type="button"
          onClick={addCustom}
          disabled={!custom.trim()}
          className="neu-button px-3 py-2 text-xs font-bold rounded-lg inline-flex items-center gap-1 disabled:opacity-50"
        >
          <Plus size={13} /> Add
        </button>
      </div>
    </div>
  );
}
