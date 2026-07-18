"use client";

// Doctor's own profile — specialty/qualifications/fee/bio/languages plus
// the government verification fields (license number, license document,
// verification status). Previously there was no frontend surface for any
// of this at all: the backend had GET/PUT /doctors/me and the upload
// endpoints, but a doctor had no page to actually use them, meaning the
// approval workflow was backend-complete but unusable end-to-end.

import React, { useEffect, useRef, useState } from 'react';
import { Stethoscope, Camera, FileUp, CheckCircle2, Clock, AlertTriangle, Save } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import { useRouter } from 'next/navigation';
import api from '../../../lib/api';

interface DoctorSelf {
  id: number;
  full_name: string;
  specialty: string;
  qualifications?: string | null;
  experience_years: number;
  consultation_fee: number;
  bio?: string | null;
  languages?: string | null;
  is_available: boolean;
  photo_url?: string | null;
  license_number?: string | null;
  license_document_url?: string | null;
  service_hours?: string | null;
  verification_status: string;
  rejection_reason?: string | null;
}

const STATUS_STYLE: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
  PENDING: { label: 'Pending Review', className: 'bg-amber-500/15 text-amber-600 border-amber-500/30', icon: <Clock size={14} /> },
  APPROVED: { label: 'Approved', className: 'bg-emerald-500/15 text-emerald-600 border-emerald-500/30', icon: <CheckCircle2 size={14} /> },
  REJECTED: { label: 'Not Approved', className: 'bg-red-500/15 text-red-600 border-red-500/30', icon: <AlertTriangle size={14} /> },
};

function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function DoctorProfilePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [profile, setProfile] = useState<DoctorSelf | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);

  const photoInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'DOCTOR') {
      router.push('/');
      return;
    }
    (async () => {
      try {
        const res = await api.get<DoctorSelf>('/doctors/me');
        setProfile(res.data);
      } catch {
        setError('Could not load your profile.');
      } finally {
        setLoading(false);
      }
    })();
  }, [user, authLoading, router]);

  const field = (key: keyof DoctorSelf, value: string) => {
    setProfile((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const save = async () => {
    if (!profile) return;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.put<DoctorSelf>('/doctors/me', {
        specialty: profile.specialty,
        qualifications: profile.qualifications,
        experience_years: profile.experience_years,
        consultation_fee: profile.consultation_fee,
        bio: profile.bio,
        languages: profile.languages,
        is_available: profile.is_available,
        license_number: profile.license_number,
        service_hours: profile.service_hours,
      });
      setProfile(res.data);
      setSuccess('Profile saved.');
    } catch {
      setError('Could not save your profile.');
    } finally {
      setSaving(false);
    }
  };

  const uploadPhoto = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingPhoto(true);
    setError('');
    try {
      const image_base64 = await readAsBase64(file);
      const res = await api.post<DoctorSelf>('/doctors/me/photo', { image_base64 });
      setProfile(res.data);
    } catch {
      setError('Photo upload failed.');
    } finally {
      setUploadingPhoto(false);
      if (photoInputRef.current) photoInputRef.current.value = '';
    }
  };

  const uploadLicenseDocument = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingDoc(true);
    setError('');
    try {
      const image_base64 = await readAsBase64(file);
      const res = await api.post<DoctorSelf>('/doctors/me/license-document', { image_base64 });
      setProfile(res.data);
      setSuccess('License document uploaded.');
    } catch {
      setError('Document upload failed.');
    } finally {
      setUploadingDoc(false);
      if (docInputRef.current) docInputRef.current.value = '';
    }
  };

  if (authLoading || loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading your profile…</div>;
  }
  if (!profile) {
    return <div className="min-h-screen flex items-center justify-center text-red-500">{error || 'Profile unavailable.'}</div>;
  }

  const status = STATUS_STYLE[profile.verification_status] || STATUS_STYLE.PENDING;

  return (
    <div className="min-h-screen p-8 lg:p-16 max-w-3xl mx-auto">
      <h1 className="text-3xl font-extrabold flex items-center gap-3 mb-2">
        <Stethoscope className="text-indigo-500" /> My Doctor Profile
      </h1>
      <p className="text-gray-500 mb-6">
        Patients see this once your application is approved by a government reviewer.
      </p>

      <div className="flex items-center gap-3 mb-8">
        <span className={`flex items-center gap-1.5 text-sm font-bold px-3 py-1.5 rounded-full border ${status.className}`}>
          {status.icon} {status.label}
        </span>
      </div>

      {profile.verification_status === 'REJECTED' && profile.rejection_reason && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-sm mb-6">
          <strong>Reviewer&apos;s reason:</strong> {profile.rejection_reason}
          <p className="mt-1 text-gray-500">Update your details below and they&apos;ll be reviewed again.</p>
        </div>
      )}

      {error && <p role="alert" className="text-red-500 font-semibold mb-4">{error}</p>}
      {success && <p role="status" className="text-emerald-500 font-semibold mb-4">{success}</p>}

      <div className="glass-panel p-6 mb-6 flex items-center gap-5">
        <div className="w-20 h-20 rounded-full overflow-hidden bg-white/10 flex items-center justify-center shrink-0">
          {profile.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={profile.photo_url} alt="Profile" className="w-full h-full object-cover" />
          ) : (
            <Stethoscope className="text-gray-400" size={28} />
          )}
        </div>
        <div>
          <input ref={photoInputRef} type="file" accept="image/*" className="hidden" onChange={uploadPhoto} />
          <button
            onClick={() => photoInputRef.current?.click()}
            disabled={uploadingPhoto}
            className="neu-button px-4 py-2 text-sm font-bold rounded-xl flex items-center gap-2 disabled:opacity-50"
          >
            <Camera size={16} /> {uploadingPhoto ? 'Uploading…' : 'Change Photo'}
          </button>
        </div>
      </div>

      <div className="glass-panel p-6 space-y-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="doc-specialty" className="block text-sm font-semibold mb-1.5">Specialty</label>
            <input
              id="doc-specialty"
              value={profile.specialty}
              onChange={(e) => field('specialty', e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="doc-qualifications" className="block text-sm font-semibold mb-1.5">Qualifications</label>
            <input
              id="doc-qualifications"
              value={profile.qualifications ?? ''}
              onChange={(e) => field('qualifications', e.target.value)}
              placeholder="e.g. MBBS, MD"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="doc-experience" className="block text-sm font-semibold mb-1.5">Experience (years)</label>
            <input
              id="doc-experience"
              type="number" min={0} max={80}
              value={profile.experience_years}
              onChange={(e) => field('experience_years', e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="doc-fee" className="block text-sm font-semibold mb-1.5">Consultation Fee (₹)</label>
            <input
              id="doc-fee"
              type="number" min={0}
              value={profile.consultation_fee}
              onChange={(e) => field('consultation_fee', e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="doc-languages" className="block text-sm font-semibold mb-1.5">Languages</label>
            <input
              id="doc-languages"
              value={profile.languages ?? ''}
              onChange={(e) => field('languages', e.target.value)}
              placeholder="Tamil, English"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="doc-hours" className="block text-sm font-semibold mb-1.5">Service Hours</label>
            <input
              id="doc-hours"
              value={profile.service_hours ?? ''}
              onChange={(e) => field('service_hours', e.target.value)}
              placeholder="Mon-Sat 9am-1pm"
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label htmlFor="doc-license" className="block text-sm font-semibold mb-1.5">
            Medical Registration / License Number
          </label>
          <input
            id="doc-license"
            value={profile.license_number ?? ''}
            onChange={(e) => field('license_number', e.target.value)}
            placeholder="e.g. TN-MED-2026-00123"
            className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
          />
          <p className="text-xs text-gray-500 mt-1">
            This is what a government reviewer checks before approving your account.
          </p>
        </div>

        <button
          onClick={save}
          disabled={saving}
          className="neu-button px-5 py-3 bg-indigo-500 text-white font-bold rounded-xl flex items-center gap-2 disabled:opacity-50"
        >
          <Save size={16} /> {saving ? 'Saving…' : 'Save Profile'}
        </button>
      </div>

      <div className="glass-panel p-6">
        <h2 className="font-bold mb-2 flex items-center gap-2"><FileUp size={18} /> License / ID Document</h2>
        <p className="text-sm text-gray-500 mb-4">
          Upload a clear photo or scan of your medical registration certificate.
        </p>
        {profile.license_document_url && (
          <a
            href={profile.license_document_url}
            target="_blank" rel="noreferrer"
            className="text-sm text-indigo-500 underline block mb-3"
          >
            View currently uploaded document
          </a>
        )}
        <input ref={docInputRef} type="file" accept="image/*,application/pdf" className="hidden" onChange={uploadLicenseDocument} />
        <button
          onClick={() => docInputRef.current?.click()}
          disabled={uploadingDoc}
          className="neu-button px-4 py-2 text-sm font-bold rounded-xl flex items-center gap-2 disabled:opacity-50"
        >
          <FileUp size={16} /> {uploadingDoc ? 'Uploading…' : profile.license_document_url ? 'Replace Document' : 'Upload Document'}
        </button>
      </div>
    </div>
  );
}
