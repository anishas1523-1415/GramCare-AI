"use client";

// Hospital's own profile — name, location, contact, departments, licence.
//
// The location half matters more here than anywhere else in the product:
// SOS routing sorts candidate hospitals by distance, so a hospital saved
// without coordinates is invisible to it and will never be sent an
// emergency. Coordinates can therefore be set three ways — picked from
// address search, dropped on the map, or taken from the device — because
// relying on the browser's location prompt alone left people stuck with a
// profile that silently could not receive anything.
//
// A new or edited profile is PENDING until a government reviewer approves
// it (modules/hospital/router.py), and that state is shown here rather than
// left for someone to wonder about.

import React, { useEffect, useRef, useState } from 'react';
import { Building2, FileUp, Save, ShieldCheck, Clock, XCircle } from 'lucide-react';
import LocationPicker from '../../../components/LocationPicker';
import DepartmentPicker from '../../../components/DepartmentPicker';
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
  verification_status?: string | null;
  verification_notes?: string | null;
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

  // Location is owned by LocationPicker, which can set all three of
  // address/lat/lng at once (picking a search result moves the pin; moving
  // the pin rewrites the address).
  const setLocation = (next: { address: string; lat: number | null; lng: number | null }) => {
    setProfile((prev) => ({ ...prev, address: next.address, lat: next.lat, lng: next.lng }));
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

      {!isNew && profile.verification_status && (
        <div
          className={`mb-4 rounded-xl border-2 p-3.5 flex items-start gap-2.5 ${
            profile.verification_status === 'APPROVED'
              ? 'border-emerald-500/60 bg-emerald-500/10'
              : profile.verification_status === 'REJECTED'
                ? 'border-red-500/60 bg-red-500/10'
                : 'border-amber-500/60 bg-amber-500/10'
          }`}
        >
          {profile.verification_status === 'APPROVED' ? (
            <ShieldCheck size={18} className="text-emerald-500 mt-0.5 shrink-0" />
          ) : profile.verification_status === 'REJECTED' ? (
            <XCircle size={18} className="text-red-500 mt-0.5 shrink-0" />
          ) : (
            <Clock size={18} className="text-amber-500 mt-0.5 shrink-0" />
          )}
          <div className="text-sm">
            <p className="font-bold">
              {profile.verification_status === 'APPROVED'
                ? 'Approved — this hospital receives emergency alerts'
                : profile.verification_status === 'REJECTED'
                  ? 'Not approved'
                  : 'Waiting for government review'}
            </p>
            <p className="text-gray-600 dark:text-gray-300">
              {profile.verification_status === 'APPROVED'
                ? 'Editing the details below sends the profile back for review.'
                : profile.verification_status === 'REJECTED'
                  ? (profile.verification_notes ?? 'Correct the details below and save to resubmit.')
                  : 'Emergency alerts are only routed to approved hospitals, so nothing will arrive until this is reviewed.'}
            </p>
          </div>
        </div>
      )}

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
        <LocationPicker
          label="Address & location on map"
          address={profile.address ?? ''}
          lat={profile.lat ?? null}
          lng={profile.lng ?? null}
          onChange={setLocation}
          hint="Emergency alerts are routed to the nearest hospital by these coordinates, so place the pin on the actual building entrance."
        />
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
        <DepartmentPicker
          label="Departments & specialities"
          value={profile.specializations ?? ''}
          onChange={(v) => field('specializations', v)}
        />


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
