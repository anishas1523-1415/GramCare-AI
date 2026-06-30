"use client";

import React, { useState, useEffect } from 'react';
import { Search, Filter, User, Clock, ShieldAlert, ChevronRight } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import api from '../../../lib/api';

export default function PatientDirectory() {
  const { user } = useAuth();
  const router = useRouter();
  
  const [patients, setPatients] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPatients = async () => {
      try {
        // In a real implementation, we'd hit /patients/all
        // Since we are mocking the UI for the directory, we'll hit EHR endpoint and extract unique patients
        const res = await api.get('/ehr/records');
        
        // Group by patient name (simplified)
        const uniquePatientsMap = new Map();
        res.data.forEach((record: any) => {
          if (!uniquePatientsMap.has(record.patient_name)) {
            uniquePatientsMap.set(record.patient_name, {
              id: record.id,
              name: record.patient_name,
              last_visit: record.timestamp,
              last_symptoms: record.symptoms,
              severity: record.ai_severity
            });
          }
        });
        
        setPatients(Array.from(uniquePatientsMap.values()));
      } catch (e) {
        console.error("Failed to fetch patients", e);
      } finally {
        setLoading(false);
      }
    };
    fetchPatients();
  }, []);

  const filteredPatients = patients.filter(p => 
    p.name.toLowerCase().includes(search.toLowerCase())
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

      {loading ? (
        <div className="text-center py-20 text-gray-500">Loading patients...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredPatients.map(patient => (
            <div key={patient.id} className="glass-panel hover:scale-[1.02] transition-transform cursor-pointer" onClick={() => alert("Navigate to full EHR view")}>
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center font-bold text-xl">
                    {patient.name.charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-800 text-lg">{patient.name}</h3>
                    <p className="text-sm text-gray-500">ID: PT-{1000 + patient.id}</p>
                  </div>
                </div>
                {patient.severity === 'CRITICAL' && (
                  <ShieldAlert className="text-red-500" />
                )}
              </div>
              
              <div className="bg-gray-50 rounded-lg p-3 mb-4">
                <p className="text-sm text-gray-600"><span className="font-bold">Last Visit:</span> {new Date(patient.last_visit).toLocaleDateString()}</p>
                <p className="text-sm text-gray-600 truncate"><span className="font-bold">Reason:</span> {patient.last_symptoms}</p>
              </div>

              <div className="flex justify-between items-center text-indigo-600 font-semibold text-sm">
                <span>View Full EHR</span>
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
