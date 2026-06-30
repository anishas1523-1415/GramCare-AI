"use client";

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, Plus, Edit2, Trash2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
// import api from '../../lib/api'; 
// Temporarily using mock data to keep UI stable during backend transition

export default function FamilyProfiles() {
  const { user } = useAuth();
  const [profiles, setProfiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  
  // Mock form state
  const [formData, setFormData] = useState({
    full_name: '',
    relation: '',
    age: '',
    gender: 'Male',
    chronic_conditions: ''
  });

  useEffect(() => {
    // Simulate API fetch for family profiles
    setTimeout(() => {
      setProfiles([
        { id: 1, full_name: "Sita Devi", relation: "Mother", age: 55, gender: "Female", chronic_conditions: "Hypertension" },
        { id: 2, full_name: "Arjun Kumar", relation: "Son", age: 12, gender: "Male", chronic_conditions: "None" }
      ]);
      setLoading(false);
    }, 800);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newProfile = {
      id: Math.random(),
      ...formData,
      age: parseInt(formData.age)
    };
    setProfiles([...profiles, newProfile]);
    setShowForm(false);
    setFormData({ full_name: '', relation: '', age: '', gender: 'Male', chronic_conditions: '' });
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to manage family profiles.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-24 relative overflow-hidden">
      {/* Background blobs */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[10%] left-[20%] w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40" />
      </div>

      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-4xl font-extrabold flex items-center gap-3"><Users className="text-indigo-500" size={40} /> Family Profiles</h1>
            <p className="text-gray-500 mt-2">Manage healthcare records for your dependents.</p>
          </div>
          <button 
            onClick={() => setShowForm(!showForm)}
            className="neu-button px-6 py-3 bg-teal-500 text-white font-bold rounded-xl flex items-center gap-2"
          >
            {showForm ? 'Cancel' : <><Plus size={20} /> Add Member</>}
          </button>
        </div>

        {showForm && (
          <motion.form 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            onSubmit={handleSubmit}
            className="glass-panel p-6 mb-8 relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-white/40 dark:bg-black/40 z-0"></div>
            <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-semibold mb-2">Full Name</label>
                <input required type="text" value={formData.full_name} onChange={(e) => setFormData({...formData, full_name: e.target.value})} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Relationship</label>
                <input required type="text" value={formData.relation} onChange={(e) => setFormData({...formData, relation: e.target.value})} placeholder="e.g. Mother, Son, Spouse" className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Age</label>
                <input required type="number" value={formData.age} onChange={(e) => setFormData({...formData, age: e.target.value})} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Gender</label>
                <select value={formData.gender} onChange={(e) => setFormData({...formData, gender: e.target.value})} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none">
                  <option>Male</option>
                  <option>Female</option>
                  <option>Other</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-semibold mb-2">Chronic Conditions (Optional)</label>
                <input type="text" value={formData.chronic_conditions} onChange={(e) => setFormData({...formData, chronic_conditions: e.target.value})} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div className="md:col-span-2 flex justify-end">
                <button type="submit" className="neu-button px-8 py-3 bg-indigo-500 text-white font-bold rounded-xl">Save Profile</button>
              </div>
            </div>
          </motion.form>
        )}

        {loading ? (
          <div className="flex justify-center p-10"><div className="animate-spin w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full"></div></div>
        ) : profiles.length === 0 ? (
          <div className="glass-panel p-10 text-center text-gray-500">No family profiles added yet.</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {profiles.map((profile) => (
              <motion.div 
                key={profile.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-panel p-6 relative overflow-hidden group hover:-translate-y-1 transition-transform"
              >
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent z-0"></div>
                <div className="relative z-10">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-2xl font-bold">{profile.full_name}</h3>
                      <span className="inline-block px-3 py-1 bg-indigo-500/10 text-indigo-500 rounded-full text-sm font-semibold mt-1">{profile.relation}</span>
                    </div>
                    <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button className="p-2 bg-white/50 dark:bg-black/50 rounded-lg hover:text-indigo-500 transition-colors"><Edit2 size={16} /></button>
                      <button className="p-2 bg-white/50 dark:bg-black/50 rounded-lg hover:text-red-500 transition-colors"><Trash2 size={16} /></button>
                    </div>
                  </div>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-gray-500">Age / Gender:</span> <span className="font-semibold">{profile.age} yrs / {profile.gender}</span></div>
                    <div className="flex justify-between"><span className="text-gray-500">Conditions:</span> <span className="font-semibold text-orange-500">{profile.chronic_conditions || 'None'}</span></div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
