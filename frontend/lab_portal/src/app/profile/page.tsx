"use client";

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, Phone, MapPin, Home, LogOut } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useLocale } from '../../contexts/LocaleContext';
import type { LabCenter } from '../../types';

export default function ProfilePage() {
  const { user, logout, loading: authLoading } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const [lab, setLab] = useState<LabCenter | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace('/login');
      return;
    }
    api.get<LabCenter>('/lab/me')
      .then((res) => setLab(res.data))
      .catch((err) => {
        if (err?.response?.status === 409) router.replace('/onboarding');
      })
      .finally(() => setLoading(false));
  }, [user, authLoading, router]);

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">{t('loading_profile')}</div>;
  }

  return (
    <div className="max-w-2xl mx-auto p-6 lg:p-10">
      <h1 className="text-2xl font-extrabold mb-6 flex items-center gap-3">
        <Building2 className="text-[var(--primary)]" size={28} /> {t('lab_profile')}
      </h1>

      {lab && (
        <div className="glass-panel p-6 space-y-4 mb-6">
          <div>
            <p className="text-xs text-gray-500 uppercase font-bold">{t('name')}</p>
            <p className="text-lg font-semibold">{lab.name}</p>
          </div>
          {lab.address && (
            <div className="flex items-center gap-2">
              <MapPin size={16} className="text-gray-400" />
              <p>{lab.address}</p>
            </div>
          )}
          {lab.phone && (
            <div className="flex items-center gap-2">
              <Phone size={16} className="text-gray-400" />
              <p>{lab.phone}</p>
            </div>
          )}
          <div className="flex items-center gap-2">
            <Home size={16} className="text-gray-400" />
            <p>{lab.offers_home_collection ? t('offers_home_collection_label') : t('in_center_only')}</p>
          </div>
          <div>
            <span className={`text-xs font-bold px-3 py-1 rounded-full ${lab.is_active ? 'bg-emerald-500/15 text-emerald-600' : 'bg-gray-400/15 text-gray-500'}`}>
              {lab.is_active ? t('active') : t('inactive')}
            </span>
          </div>
        </div>
      )}

      <div className="glass-panel p-6">
        <p className="text-sm text-gray-500 mb-4">
          {t('signed_in_as')} <span className="font-semibold">{user?.full_name || user?.username}</span> ({user?.email})
        </p>
        <button
          onClick={logout}
          className="neu-button w-full py-3 bg-red-500 text-white font-bold rounded-xl flex items-center justify-center gap-2"
        >
          <LogOut size={18} /> {t('logout')}
        </button>
      </div>
    </div>
  );
}
