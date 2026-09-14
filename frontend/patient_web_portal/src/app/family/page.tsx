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
import { useLocale } from '../../contexts/LocaleContext';
import ThemedLoader from '../../components/ThemedLoader';
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
  const { t } = useLocale();
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
      setError(typeof message === 'string' ? message : t('failed_save_profile'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (p: FamilyProfile) => {
    if (!window.confirm(`${t('remove_profile_confirm')} ${p.full_name}?`)) return;
    try {
      await api.delete(`/family/${p.id}`);
      if (activeProfile?.id === p.id) setActiveProfile(null);
      await refreshProfiles();
    } catch {
      setError(t('failed_delete_profile'));
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">{t('please_login_family')}</p>
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
              <Users className="text-indigo-500" size={40} /> {t('nav_family_profiles')}
            </h1>
            <p className="text-gray-500 mt-2">{t('family_subtitle')}</p>
          </div>
          <button
            onClick={() => { setShowForm(!showForm); setEditing(null); setFormData(emptyForm); setError(''); }}
            className="neu-button px-6 py-3 bg-teal-500 text-white font-bold rounded-xl flex items-center gap-2"
          >
            {showForm ? t('cancel') : <><Plus size={20} /> {t('add_member')}</>}
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
                <label htmlFor="family-fullname" className="block text-sm font-semibold mb-2">{t('full_name_label')}</label>
                <input id="family-fullname" required type="text" value={formData.full_name} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label htmlFor="family-relation" className="block text-sm font-semibold mb-2">{t('relationship_label')}</label>
                <input id="family-relation" required type="text" value={formData.relation} onChange={(e) => setFormData({ ...formData, relation: e.target.value })} placeholder={t('relationship_placeholder')} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label htmlFor="family-age" className="block text-sm font-semibold mb-2">{t('age_label')}</label>
                <input id="family-age" required type="number" min={0} max={150} value={formData.age} onChange={(e) => setFormData({ ...formData, age: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label htmlFor="family-gender" className="block text-sm font-semibold mb-2">{t('gender_label')}</label>
                <select id="family-gender" value={formData.gender} onChange={(e) => setFormData({ ...formData, gender: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none">
                  <option>Male</option>
                  <option>Female</option>
                  <option>Other</option>
                </select>
              </div>
              <div>
                <label htmlFor="family-blood" className="block text-sm font-semibold mb-2">{t('blood_group_optional')}</label>
                <input id="family-blood" type="text" value={formData.blood_group} onChange={(e) => setFormData({ ...formData, blood_group: e.target.value })} placeholder="e.g. O+" className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div>
                <label htmlFor="family-conditions" className="block text-sm font-semibold mb-2">{t('chronic_conditions_optional')}</label>
                <input id="family-conditions" type="text" value={formData.chronic_conditions} onChange={(e) => setFormData({ ...formData, chronic_conditions: e.target.value })} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-500 outline-none" />
              </div>
              <div className="md:col-span-2 flex justify-end">
                <button type="submit" disabled={submitting} className="neu-button px-8 py-3 bg-indigo-500 text-white font-bold rounded-xl disabled:opacity-50">
                  {submitting ? t('saving_ellipsis') : editing ? t('update_profile') : t('save_profile')}
                </button>
              </div>
            </div>
          </motion.form>
        )}

        {loading ? (
          <ThemedLoader variant="wallet" label={t('loading_family_profiles')} />
        ) : profiles.length === 0 ? (
          <div className="glass-panel p-10 text-center text-gray-500">
            {t('no_family_profiles')}
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
                    <div className="flex justify-between"><span className="text-gray-500">{t('age_gender_label')}:</span> <span className="font-semibold">{profile.age} {t('years_short')} / {profile.gender}</span></div>
                    {profile.blood_group && (
                      <div className="flex justify-between"><span className="text-gray-500">{t('blood_group_label')}:</span> <span className="font-semibold">{profile.blood_group}</span></div>
                    )}
                    <div className="flex justify-between"><span className="text-gray-500">{t('conditions_label')}:</span> <span className="font-semibold text-orange-500">{profile.chronic_conditions || t('none_label')}</span></div>
                  </div>

                  <button
                    onClick={() => setActiveProfile(activeProfile?.id === profile.id ? null : profile)}
                    className={`mt-4 w-full py-2 rounded-xl font-bold text-sm transition-colors ${activeProfile?.id === profile.id ? 'bg-teal-500 text-white' : 'bg-white/40 dark:bg-black/40 hover:bg-teal-500/20'}`}
                  >
                    {activeProfile?.id === profile.id ? t('currently_selected') : t('act_for_member')}
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
