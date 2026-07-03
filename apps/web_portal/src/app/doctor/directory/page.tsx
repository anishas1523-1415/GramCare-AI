"use client";

import React, { useState, useEffect } from 'react';
import { Search, Filter, ChevronRight } from 'lucide-react';
import api from '../../../lib/api';
import type { EHRRecord } from '../../../types';

interface DirectoryEntry {
  patientId: number;
  lastVisit: string;
  lastTitle: string;
  lastType: string;
  recordCount: number;
}

export default function PatientDirectory() {
  const [patients, setPatients] = useState<DirectoryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchPatients = async () => {
      try {
        // GET /ehr/records (doctor-only) — previously this page called a
        // route that didn't exist, so it always failed. Group the recent
        // records feed by patient.
        const res = await api.get<EHRRecord[]>('/ehr/records');

        const byPatient = new Map<number, DirectoryEntry>();
        res.data.forEach((record) => {
          const existing = byPatient.get(record.patient_id);
          if (existing) {
            existing.recordCount += 1;
          } else {
            byPatient.set(record.patient_id, {
              patientId: record.patient_id,
              lastVisit: record.record_date || record.created_at,
              lastTitle: record.title || record.content.slice(0, 80),
              lastType: record.record_type,
              recordCount: 1,
            });
          }
        });

        setPatients(Array.from(byPatient.values()));
      } catch (e) {
        console.error("Failed to fetch patients", e);
        setError('Could not load the directory (doctors only).');
      } finally {
        setLoading(false);
      }
    };
    fetchPatients();
  }, []);

  const filteredPatients = patients.filter(p =>
    String(p.patientId).includes(search) || p.lastTitle.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">Patient Directory</h1>
          <p className="text-gray-500">Search and view historical Electronic Health Records (EHR)</p>
        </div>
      </div>

      <div className="neo-glass-container p-6 mb-8 flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
          <input 
            type="text"
            placeholder="Search patient name or ID..."
            className="w-full bg-gray-100 rounded-xl py-3 pl-12 pr-4 outline-none focus:ring-2 focus:ring-indigo-500"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button className="neu-button px-6 flex items-center gap-2">
          <Filter size={20} /> Filter
        </button>
      </div>

      {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

      {loading ? (
        <div className="text-center py-20 text-gray-500">Loading patients...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPatients.map(patient => (
            <div key={patient.patientId} className="glass-panel p-6 hover:scale-[1.02] transition-transform">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center font-bold text-xl">
                    #{patient.patientId}
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800 text-lg">Patient #{patient.patientId}</h3>
                    <p className="text-sm text-gray-500">{patient.recordCount} record{patient.recordCount === 1 ? '' : 's'}</p>
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-3 mb-4">
                <p className="text-sm text-gray-600"><span className="font-bold">Last record:</span> {new Date(patient.lastVisit).toLocaleDateString()}</p>
                <p className="text-sm text-gray-600 truncate"><span className="font-bold">{patient.lastType}:</span> {patient.lastTitle}</p>
              </div>

              <div className="flex justify-between items-center text-indigo-600 font-semibold text-sm">
                <span>Latest activity</span>
                <ChevronRight size={16} />
              </div>
            </div>
          ))}

          {filteredPatients.length === 0 && (
            <div className="col-span-full text-center py-10 text-gray-500">
              No patients found matching your search.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
