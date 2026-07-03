"use client";

// Site-wide navigation. Previously there was no way to reach /login (which
// itself didn't exist) or any other page from the homepage — no header/nav
// component existed anywhere in the app.

import Link from 'next/link';
import { useAuth } from '../contexts/AuthContext';
import { useProfile } from '../contexts/ProfileContext';

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
      className="px-3 py-2 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm font-semibold"
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

  return (
    <header className="w-full flex items-center justify-between px-6 py-4 relative z-20">
      <Link href="/" className="font-extrabold text-lg text-[var(--foreground)]">
        GramCare <span className="text-teal-500">AI</span>
      </Link>

      <nav className="flex items-center gap-4 text-sm font-semibold">
        {loading ? null : user ? (
          <>
            {user.role === 'PATIENT' && (
              <>
                <Link href="/book" className="hover:text-teal-500 transition-colors">Book Consultation</Link>
                <Link href="/family" className="hover:text-teal-500 transition-colors">Family Profiles</Link>
                <Link href="/prescriptions" className="hover:text-teal-500 transition-colors">My Prescriptions</Link>
                <Link href="/pharmacy" className="hover:text-teal-500 transition-colors">Find Medicine</Link>
                <ProfileSwitcher />
              </>
            )}
            {user.role === 'DOCTOR' && (
              <Link href="/doctor/dashboard" className="hover:text-teal-500 transition-colors">Doctor Dashboard</Link>
            )}
            <span className="text-gray-500">
              {user.full_name || user.username} ({user.role})
            </span>
            <button
              onClick={logout}
              className="neu-button px-4 py-2 font-bold rounded-lg"
            >
              Sign Out
            </button>
          </>
        ) : (
          <Link href="/login" className="neu-button px-4 py-2 bg-indigo-500 text-white font-bold rounded-lg">
            Sign In
          </Link>
        )}
      </nav>
    </header>
  );
}
