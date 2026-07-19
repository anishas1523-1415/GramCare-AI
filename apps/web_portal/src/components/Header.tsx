"use client";

// Site-wide navigation. Previously there was no way to reach /login (which
// itself didn't exist) or any other page from the homepage — no header/nav
// component existed anywhere in the app.
//
// Grew role-by-role (patient links, doctor links, hospital links, profile
// switcher, device manager, sign out) into a single flat row that wraps
// messily on anything narrower than a wide desktop — collapses into a
// toggleable menu below the `md` breakpoint instead.

import { useState } from 'react';
import Link from 'next/link';
import { Menu, X } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useProfile } from '../contexts/ProfileContext';
import { useLocale } from '../contexts/LocaleContext';

/** English/Tamil toggle — visible whether or not the user is signed in,
 * since the login/register screen (the first thing an unauthenticated
 * visitor sees) is exactly where this matters most. */
function LanguageSwitcher() {
  const { code, setCode, t } = useLocale();
  return (
    <div className="flex rounded-lg overflow-hidden border border-white/20 text-xs font-bold shrink-0" aria-label={t('language')}>
      <button
        type="button"
        onClick={() => setCode('en')}
        className={`px-2.5 py-1.5 transition-colors ${code === 'en' ? 'bg-indigo-500 text-white' : 'bg-white/40 dark:bg-black/20'}`}
        aria-pressed={code === 'en'}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setCode('ta')}
        className={`px-2.5 py-1.5 transition-colors ${code === 'ta' ? 'bg-indigo-500 text-white' : 'bg-white/40 dark:bg-black/20'}`}
        aria-pressed={code === 'ta'}
      >
        தமிழ்
      </button>
    </div>
  );
}

/** "Acting for" switcher — the planning doc's family-member selection,
 * available everywhere so triage/booking/records are scoped correctly. */
function ProfileSwitcher() {
  const { profiles, activeProfile, setActiveProfile } = useProfile();
  if (profiles.length === 0) return null;

  return (
    <select
      aria-label="Select family member"
      value={activeProfile?.id ?? ''}
      onChange={(e) => {
        const id = e.target.value;
        setActiveProfile(id === '' ? null : profiles.find((p) => p.id === Number(id)) || null);
      }}
      className="w-full md:w-auto px-3 py-2 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm font-semibold"
      style={activeProfile?.color_tag ? { borderColor: activeProfile.color_tag } : undefined}
    >
      <option value="">Myself</option>
      {profiles.map((p) => (
        <option key={p.id} value={p.id}>
          {p.full_name} ({p.relation})
        </option>
      ))}
    </select>
  );
}

export default function Header() {
  const { user, loading, logout } = useAuth();
  const { t } = useLocale();
  const [menuOpen, setMenuOpen] = useState(false);

  const ROLE_LABEL: Record<string, string> = {
    PATIENT: t('role_patient'),
    DOCTOR: t('role_doctor'),
    HOSPITAL: t('role_hospital'),
    PHARMACIST: t('role_pharmacist'),
    LAB: t('role_lab'),
    ADMIN: t('role_admin'),
  };

  const navLinks = user ? (
    <>
      {user.role === 'PATIENT' && (
        <>
          <Link href="/sos" className="text-red-500 font-bold hover:text-red-400 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_sos')}</Link>
          <Link href="/symptom-checker" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_symptom_checker')}</Link>
          <Link href="/book" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_book_consultation')}</Link>
          <Link href="/family" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_family_profiles')}</Link>
          <Link href="/prescriptions" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_my_prescriptions')}</Link>
          <Link href="/pharmacy" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_find_medicine')}</Link>
          <Link href="/lab-tests" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_lab_tests')}</Link>
          <Link href="/passport" className="hover:text-red-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_health_passport')}</Link>
          <ProfileSwitcher />
        </>
      )}
      {user.role === 'DOCTOR' && (
        <>
          <Link href="/doctor/dashboard" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_doctor_dashboard')}</Link>
          <Link href="/doctor/directory" className="hover:text-teal-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_patient_directory')}</Link>
          <Link href="/doctor/analytics" className="hover:text-purple-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_health_intelligence')}</Link>
          <Link href="/doctor/profile" className="hover:text-indigo-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_my_profile')}</Link>
          <Link href="/hospital" className="hover:text-red-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_emergency_desk')}</Link>
        </>
      )}
      {(user.role === 'HOSPITAL' || user.role === 'ADMIN') && (
        <>
          <Link href="/hospital" className="hover:text-red-500 transition-colors font-bold" onClick={() => setMenuOpen(false)}>{t('nav_emergency_desk')}</Link>
          <Link href="/authority" className="hover:text-purple-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_health_intelligence')}</Link>
        </>
      )}
      {user.role === 'HOSPITAL' && (
        <Link href="/hospital/profile" className="hover:text-red-500 transition-colors" onClick={() => setMenuOpen(false)}>{t('nav_hospital_profile')}</Link>
      )}
      <span className="text-gray-500 md:order-last">
        {user.full_name || user.username} ({ROLE_LABEL[user.role] || user.role})
      </span>
      <Link href="/account/sessions" className="hover:text-teal-500 transition-colors" title="Manage signed-in devices" onClick={() => setMenuOpen(false)}>
        {t('nav_my_devices')}
      </Link>
      <button
        onClick={() => { setMenuOpen(false); logout(); }}
        className="neu-button px-4 py-2 font-bold rounded-lg w-full md:w-auto"
      >
        {t('sign_out')}
      </button>
    </>
  ) : (
    <Link href="/login" className="neu-button px-4 py-2 bg-indigo-500 text-white font-bold rounded-lg w-full md:w-auto text-center" onClick={() => setMenuOpen(false)}>
      {t('sign_in')}
    </Link>
  );

  return (
    <header className="w-full px-6 py-4 relative z-20">
      <div className="flex items-center justify-between">
        <Link href="/" className="font-extrabold text-lg text-[var(--foreground)]">
          GramCare <span className="text-teal-500">AI</span>
        </Link>

        {/* Desktop: full row, unchanged. Below `md`, the row gets replaced
            by a toggle button so a role with many links never wraps into a
            crowded multi-line mess on a phone-width screen. */}
        <nav className="hidden md:flex items-center gap-4 text-sm font-semibold">
          {loading ? null : navLinks}
          <LanguageSwitcher />
        </nav>

        <div className="md:hidden flex items-center gap-3">
          <LanguageSwitcher />
          {!loading && (
            <button
              type="button"
              className="neu-button p-2 rounded-lg"
              onClick={() => setMenuOpen((v) => !v)}
              aria-expanded={menuOpen}
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            >
              {menuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          )}
        </div>
      </div>

      {!loading && menuOpen && (
        <nav className="md:hidden flex flex-col items-stretch gap-3 text-sm font-semibold mt-4 pb-2">
          {navLinks}
        </nav>
      )}
    </header>
  );
}
