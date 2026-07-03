"use client";

// Family Profiles — now fully wired to the backend (/api/v1/family).
// Previously this page used hardcoded mock data held in React state that
// vanished on refresh; the planning doc's "one box per family member"
// foundation did not talk to the server at all.

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Users, Plus, Edit2, Trash2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useProfile } from '../../contexts/ProfileContext';
import api from '../../lib/api';
import type { FamilyProfile } from '../../types';

const COLOR_TAGS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

interface FormState {
  full_name: string;
  relation: string;
  age: string;
  gender: string;
  blood_group: string;
  chronic_conditions: string;
}

const emptyForm: FormState = {
  full_name: '', relation: '', age: '', gender: 'Male',
  blood_group: '', chronic_conditions: '',
};

export default function FamilyProfiles() {
  const { user } = useAuth();
  const { profiles, refreshProfiles, activeProfile, setActiveProfile, loading } = useProfile();
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<FamilyProfile | null>(null);
  const [formData, setFormData] = useState<FormState>(emptyForm);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const startEdit = (p: FamilyProfile) => {
    setEditing(p);
    setFormData({
      full_name: p.full_name,
      relation: p.relation,
      age: String(p.age),
      gender: p.gender,
      blood_group: p.blood_group || '',
      chronic_conditions: p.chronic_conditions || '',
    });
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const body = {
        full_name: formData.full_name,
        relation: formData.relation,
        age: parseInt(formData.age, 10),
        gender: formData.gender,
        blood_group: formData.blood_group || null,
        chronic_conditions: formData.chronic_conditions || null,
        // Assign a stable accent color for the profile chip (accessibility
        // aid from the planning discussion's color-coding requirement).
        color_tag: editing?.color_tag || COLOR_TAGS[profiles.length % COLOR_TAGS.length],
      };
      if (editing) {
        await api.put(`/family/${editing.id}`, body);
      } else {
        await api.post('/family', body);
      }
      await refreshProfiles();
      setShowForm(false);
      setEditing(null);
      setFormData(emptyForm);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Failed to save profile. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (p: FamilyProfile) => {
    if (!window.confirm(`Remove ${p.full_name}'s profile? Their health records will be kept.`)) return;
    try {
      await api.delete(`/family/${p.id}`);
      if (activeProfile?.id === p.id) setActiveProfile(null);
      await refreshProfiles();
    } catch {
      setError('Failed to delete profile.');
    }
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
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[10%] left-[20%] w-96 h-96 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40" />
      </div>

      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-10">
          <div>
            <h1 className="text-4xl font-extrabold flex items-center gap-3">
              <Users className="text-indigo-500" size={40} /> Family Profiles
            </h1>
            <p className="text-gray-500 mt-2">Manage healthcare records for your dependents.</p>
          </div>
          <button
            onClick={() => { setShowForm(!showForm); setEditing(null); setFormData(emptyForm); setError(''); }}
            className="neu-button px-6 py-3 bg-teal-500 text-white font-bold rounded-xl flex items-center gap-2"
          >
            {showForm ? 'Cancel' : <><Plus size={20} /> Add Member</>}
          </button>
        </div>

        {error && (
          <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>
        )}

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
                <input required type="text" value={formData.full_name} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Relationship</label>
                <input required type="text" value={formData.relation} onChange={(e) => setFormData({ ...formData, relation: e.target.value })} placeholder="e.g. Mother, Son, Spouse" className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Age</label>
                <input required type="number" min={0} max={150} value={formData.age} onChange={(e) => setFormData({ ...formData, age: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Gender</label>
                <select value={formData.gender} onChange={(e) => setFormData({ ...formData, gender: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none">
                  <option>Male</option>
                  <option>Female</option>
                  <option>Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Blood Group (Optional)</label>
                <input type="text" value={formData.blood_group} onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })} placeholder="e.g. O+" className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2">Chronic Conditions (Optional)</label>
                <input type="text" value={formData.chronic_conditions} onChange={(e) => setFormData({ ...formData, chronic_conditions: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div className="md:col-span-2 flex justify-end">
                <button type="submit" disabled={submitting} className="neu-button px-8 py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-50">
                  {submitting ? 'Saving...' : editing ? 'Update Profile' : 'Save Profile'}
                </button>
              </div>
            </div>
          </motion.form>
        )}

        {loading ? (
          <div className="flex justify-center p-10"><div className="animate-spin w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full"></div></div>
        ) : profiles.length === 0 ? (
          <div className="glass-panel p-10 text-center text-gray-500">
            No family profiles added yet. Add your family members to keep their health records in one place.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {profiles.map((profile) => (
              <motion.div
                key={profile.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className={`glass-panel p-6 relative overflow-hidden group hover:-translate-y-1 transition-transform ${activeProfile?.id === profile.id ? 'ring-2 ring-teal-400' : ''}`}
              >
                <div
                  className="absolute inset-x-0 top-0 h-1.5 z-10"
                  style={{ backgroundColor: profile.color_tag || '#6366f1' }}
                />
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent z-0"></div>
                <div className="relative z-10">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-2xl font-bold">{profile.full_name}</h3>
                      <span className="inline-block px-3 py-1 bg-indigo-500/10 text-indigo-500 rounded-full text-sm font-semibold mt-1">{profile.relation}</span>
                    </div>
                    <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button aria-label={`Edit ${profile.full_name}`} onClick={() => startEdit(profile)} className="p-2 bg-white/50 dark:bg-black/50 rounded-lg hover:text-indigo-500 transition-colors"><Edit2 size={16} /></button>
                      <button aria-label={`Delete ${profile.full_name}`} onClick={() => handleDelete(profile)} className="p-2 bg-white/50 dark:bg-black/50 rounded-lg hover:text-red-500 transition-colors"><Trash2 size={16} /></button>
                    </div>
                  </div>

                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-gray-500">Age / Gender:</span> <span className="font-semibold">{profile.age} yrs / {profile.gender}</span></div>
                    {profile.blood_group && (
                      <div className="flex justify-between"><span className="text-gray-500">Blood Group:</span> <span className="font-semibold">{profile.blood_group}</span></div>
                    )}
                    <div className="flex justify-between"><span className="text-gray-500">Conditions:</span> <span className="font-semibold text-orange-500">{profile.chronic_conditions || 'None'}</span></div>
                  </div>

                  <button
                    onClick={() => setActiveProfile(activeProfile?.id === profile.id ? null : profile)}
                    className={`mt-4 w-full py-2 rounded-xl font-bold text-sm transition-colors ${activeProfile?.id === profile.id ? 'bg-teal-500 text-white' : 'bg-white/40 dark:bg-black/40 hover:bg-teal-500/20'}`}
                  >
                    {activeProfile?.id === profile.id ? 'Currently Selected' : 'Act for this member'}
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
