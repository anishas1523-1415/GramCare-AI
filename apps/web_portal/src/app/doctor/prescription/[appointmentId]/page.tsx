"use client";

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, Plus, Trash2, Printer } from 'lucide-react';
import { useRouter } from 'next/navigation';
import api from '../../../../lib/api';

export default function PrescriptionWriter({ params }: { params: { appointmentId: string } }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [diagnosis, setDiagnosis] = useState('');
  const [notes, setNotes] = useState('');
  const [medicines, setMedicines] = useState([
    { name: '', dosage: '', frequency: '1-0-1', duration: '5 days' }
  ]);

  const addMedicine = () => {
    setMedicines([...medicines, { name: '', dosage: '', frequency: '1-0-1', duration: '5 days' }]);
  };

  const removeMedicine = (index: number) => {
    setMedicines(medicines.filter((_, i) => i !== index));
  };

  const updateMedicine = (index: number, field: string, value: string) => {
    const updated = [...medicines];
    updated[index] = { ...updated[index], [field]: value };
    setMedicines(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await api.post('/ehr/issue_prescription', {
        appointment_id: parseInt(params.appointmentId),
        patient_id: 1, // Usually extracted from appointment details
        medicines: medicines,
        diagnosis,
        notes,
        dosage_instructions: "Follow strictly after meals unless specified."
      });
      alert("Prescription saved and sent to pharmacy!");
      router.push('/doctor/dashboard');
    } catch (error) {
      alert("Failed to issue prescription.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen p-8 lg:p-24 relative overflow-hidden bg-[var(--background)]">
      <div className="absolute top-[20%] left-[-10%] w-[500px] h-[500px] bg-indigo-500 rounded-full mix-blend-multiply filter blur-[100px] opacity-10 -z-10" />

      <div className="max-w-4xl mx-auto">
        <header className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3"><FileText className="text-indigo-500" /> Digital Prescription</h1>
            <p className="text-gray-500 mt-1">Appointment #{params.appointmentId}</p>
          </div>
          <button className="neu-button px-4 py-2 flex items-center gap-2 font-bold text-gray-700 dark:text-gray-200">
            <Printer size={18} /> Print
          </button>
        </header>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="glass-panel p-6">
            <h2 className="text-xl font-bold mb-4">Diagnosis & Notes</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-semibold mb-2">Primary Diagnosis</label>
                <input 
                  required
                  type="text" 
                  value={diagnosis} 
                  onChange={e => setDiagnosis(e.target.value)}
                  placeholder="e.g. Viral Infection"
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" 
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Clinical Notes</label>
                <textarea 
                  value={notes} 
                  onChange={e => setNotes(e.target.value)}
                  placeholder="Additional observations..."
                  className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none resize-none" 
                  rows={2}
                />
              </div>
            </div>
          </div>

          <div className="glass-panel p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-bold">Medicines</h2>
              <button 
                type="button" 
                onClick={addMedicine}
                className="px-4 py-2 bg-indigo-500/10 text-indigo-500 font-bold rounded-lg flex items-center gap-2 hover:bg-indigo-500 hover:text-white transition-colors"
              >
                <Plus size={16} /> Add Medicine
              </button>
            </div>

            <div className="space-y-4">
              {medicines.map((med, index) => (
                <motion.div 
                  key={index} 
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end bg-white/40 dark:bg-black/40 p-4 rounded-xl border border-white/20 relative"
                >
                  <div className="md:col-span-4">
                    <label className="block text-xs font-semibold mb-1 text-gray-500">Medicine Name</label>
                    <input 
                      required
                      type="text" 
                      value={med.name} 
                      onChange={e => updateMedicine(index, 'name', e.target.value)}
                      placeholder="e.g. Paracetamol"
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none" 
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold mb-1 text-gray-500">Dosage</label>
                    <input 
                      required
                      type="text" 
                      value={med.dosage} 
                      onChange={e => updateMedicine(index, 'dosage', e.target.value)}
                      placeholder="500mg"
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none" 
                    />
                  </div>
                  <div className="md:col-span-3">
                    <label className="block text-xs font-semibold mb-1 text-gray-500">Frequency</label>
                    <select 
                      value={med.frequency} 
                      onChange={e => updateMedicine(index, 'frequency', e.target.value)}
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none" 
                    >
                      <option>1-0-1 (Morning & Night)</option>
                      <option>1-1-1 (Three times a day)</option>
                      <option>1-0-0 (Morning only)</option>
                      <option>0-0-1 (Night only)</option>
                      <option>SOS (As needed)</option>
                    </select>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold mb-1 text-gray-500">Duration</label>
                    <input 
                      required
                      type="text" 
                      value={med.duration} 
                      onChange={e => updateMedicine(index, 'duration', e.target.value)}
                      placeholder="5 days"
                      className="w-full p-2 rounded-lg bg-[var(--background)] border border-transparent focus:ring-2 focus:ring-teal-500 outline-none" 
                    />
                  </div>
                  <div className="md:col-span-1 flex justify-end">
                    <button 
                      type="button" 
                      onClick={() => removeMedicine(index)}
                      disabled={medicines.length === 1}
                      className="p-2 bg-red-500/10 text-red-500 rounded-lg hover:bg-red-500 hover:text-white transition-colors disabled:opacity-30"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          <div className="flex justify-end pt-4">
            <button 
              type="submit" 
              disabled={loading}
              className="neu-button px-10 py-4 bg-teal-500 text-white font-bold rounded-xl text-lg disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? "Sending..." : "Issue E-Prescription"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
