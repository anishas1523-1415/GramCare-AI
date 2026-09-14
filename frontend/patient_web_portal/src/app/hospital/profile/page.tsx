"use client";

// Hospital's own profile — name, address, established year, service
// timing, specializations, license number/document. Data-collection only
// (instant access, no government approval gate, unlike the doctor
// workflow). Mirrors /doctor/profile's structure and the
// register-then-fill-in-details pattern already used by the Pharmacy
// dashboard (react_dashboard) and Lab portal.

import React, { useEffect, useRef, useState } from 'react';
import { Building2, FileUp, Save, MapPin } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useLocale } from '../../../contexts/LocaleContext';
import { useRouter } from 'next/navigation';
import api from '../../../lib/api';

interface HospitalSelf {
  id: number;
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  phone?: string | null;
  established_year?: number | null;
  service_timing?: string | null;
  specializations?: string | null;
  license_number?: string | null;
  license_document_url?: string | null;
}

function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const EMPTY: HospitalSelf = { id: 0, name: '' };

export default function HospitalProfilePage() {
  const { user, loading: authLoading } = useAuth();
  const { t } = useLocale();
  const router = useRouter();

  const [profile, setProfile] = useState<HospitalSelf>(EMPTY);
  const [isNew, setIsNew] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const docInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user || (user.role !== 'HOSPITAL' && user.role !== 'ADMIN')) {
      router.push('/');
      return;
    }
    (async () => {
      try {
        const res = await api.get<HospitalSelf>('/hospital/me');
        setProfile(res.data);
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 409) {
          setIsNew(true); // no hospital registered yet — show the same form, empty
        } else {
          setError(t('could_not_load_hospital_profile'));
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, router]);

  const field = (key: keyof HospitalSelf, value: string) => {
    setProfile((prev) => ({ ...prev, [key]: value }));
  };

  const useMyLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setProfile((prev) => ({
          ...prev,
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        }));
      },
      () => setError(t('could_not_access_location')),
    );
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.post<HospitalSelf>('/hospital/register', {
        name: profile.name,
        address: profile.address || undefined,
        lat: profile.lat ?? undefined,
        lng: profile.lng ?? undefined,
        phone: profile.phone || undefined,
        established_year: profile.established_year ? Number(profile.established_year) : undefined,
        service_timing: profile.service_timing || undefined,
        specializations: profile.specializations || undefined,
        license_number: profile.license_number || undefined,
      });
      setProfile(res.data);
      setIsNew(false);
      setSuccess(t('hospital_profile_saved'));
    } catch {
      setError(t('could_not_save_hospital_profile'));
    } finally {
      setSaving(false);
    }
  };

  const uploadLicenseDocument = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || isNew) return; // must register first — no hospital id to attach the doc to
    setUploadingDoc(true);
    setError('');
    try {
      const image_base64 = await readAsBase64(file);
      const res = await api.post<HospitalSelf>('/hospital/me/license-document', { image_base64 });
      setProfile(res.data);
      setSuccess(t('license_document_uploaded'));
    } catch {
      setError(t('document_upload_failed'));
    } finally {
      setUploadingDoc(false);
      if (docInputRef.current) docInputRef.current.value = '';
    }
  };

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">{t('loading_hospital_profile')}</div>;
  }

  return (
    <div className="min-h-screen p-8 lg:p-16 max-w-3xl mx-auto">
      <h1 className="text-3xl font-extrabold flex items-center gap-3 mb-2">
        <Building2 className="text-red-500" /> {isNew ? t('register_your_hospital') : t('nav_hospital_profile')}
      </h1>
      <p className="text-gray-500 mb-6">
        {t('hospital_profile_subtitle')}
      </p>

      {error && <p role="alert" className="text-red-500 font-semibold mb-4">{error}</p>}
      {success && <p role="status" className="text-emerald-500 font-semibold mb-4">{success}</p>}

      <form onSubmit={save} className="glass-panel p-6 space-y-4 mb-6">
        <div>
          <label htmlFor="hosp-name" className="block text-sm font-semibold mb-1.5">{t('hospital_name_label')}</label>
          <input
            id="hosp-name"
            required
            value={profile.name}
            onChange={(e) => field('name', e.target.value)}
            className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
          />
        </div>
        <div>
          <label htmlFor="hosp-address" className="block text-sm font-semibold mb-1.5">Address</label>
          <input
            id="hosp-address"
            value={profile.address ?? ''}
            onChange={(e) => field('address', e.target.value)}
            className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="hosp-phone" className="block text-sm font-semibold mb-1.5">Phone</label>
            <input
              id="hosp-phone"
              value={profile.phone ?? ''}
              onChange={(e) => field('phone', e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="hosp-established" className="block text-sm font-semibold mb-1.5">Established Year</label>
            <input
              id="hosp-established"
              type="number" min={1800} max={2100}
              value={profile.established_year ?? ''}
              onChange={(e) => field('established_year', e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="hosp-timing" className="block text-sm font-semibold mb-1.5">Service Timing</label>
            <input
              id="hosp-timing"
              value={profile.service_timing ?? ''}
              onChange={(e) => field('service_timing', e.target.value)}
              placeholder="24/7 or Mon-Sat 8am-8pm"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="hosp-license" className="block text-sm font-semibold mb-1.5">License Number</label>
            <input
              id="hosp-license"
              value={profile.license_number ?? ''}
              onChange={(e) => field('license_number', e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
            />
          </div>
        </div>
        <div>
          <label htmlFor="hosp-specializations" className="block text-sm font-semibold mb-1.5">Specializations / Departments</label>
          <input
            id="hosp-specializations"
            value={profile.specializations ?? ''}
            onChange={(e) => field('specializations', e.target.value)}
            placeholder="General Medicine, Pediatrics, Orthopedics"
            className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-red-400 focus:outline-none"
          />
        </div>
        <button
          type="button"
          onClick={useMyLocation}
          className="text-sm font-semibold text-red-500 flex items-center gap-1"
        >
          <MapPin size={14} /> {t('use_my_current_location')}
        </button>

        <button
          type="submit"
          disabled={saving}
          className="neu-button px-5 py-3 bg-red-500 text-white font-bold rounded-xl flex items-center gap-2 disabled:opacity-50"
        >
          <Save size={16} /> {saving ? t('saving_ellipsis') : isNew ? t('register_hospital') : t('save_profile')}
        </button>
      </form>

      {!isNew && (
        <div className="glass-panel p-6">
          <h2 className="font-bold mb-2 flex items-center gap-2"><FileUp size={18} /> {t('license_document')}</h2>
          <p className="text-sm text-gray-500 mb-4">{t('license_document_note')}</p>
          {profile.license_document_url && (
            <a
              href={profile.license_document_url}
              target="_blank" rel="noreferrer"
              className="text-sm text-red-500 underline block mb-3"
            >
              {t('view_document')}
            </a>
          )}
          <input ref={docInputRef} type="file" accept="image/*,application/pdf" className="hidden" onChange={uploadLicenseDocument} />
          <button
            onClick={() => docInputRef.current?.click()}
            disabled={uploadingDoc}
            className="neu-button px-4 py-2 text-sm font-bold rounded-xl flex items-center gap-2 disabled:opacity-50"
          >
            <FileUp size={16} /> {uploadingDoc ? t('uploading_ellipsis') : profile.license_document_url ? t('replace_document') : t('upload_document')}
          </button>
        </div>
      )}
    </div>
  );
}
