"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FlaskConical, LayoutDashboard, BookOpen, UserCircle, LogOut } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useLocale } from '../contexts/LocaleContext';

// Labels are locale keys, resolved at render so the nav follows a
// language switch without remounting.
const NAV = [
  { href: '/dashboard', labelKey: 'booking_queue', icon: LayoutDashboard },
  { href: '/catalog', labelKey: 'test_catalog', icon: BookOpen },
  { href: '/profile', labelKey: 'profile', icon: UserCircle },
];

export default function Header() {
  const { user, logout } = useAuth();
  const { t, code, setCode } = useLocale();
  const pathname = usePathname();

  if (!user || pathname === '/login' || pathname === '/onboarding') return null;

  return (
    <header className="sticky top-0 z-40 px-4 py-3 lg:px-8">
      <div className="glass-panel max-w-6xl mx-auto flex items-center justify-between px-5 py-3">
        <Link href="/dashboard" className="flex items-center gap-2 font-extrabold text-lg text-[var(--primary)]">
          <FlaskConical size={24} /> {t('lab_portal')}
        </Link>
        <nav className="flex items-center gap-1">
          {NAV.map(({ href, labelKey, icon: Icon }) => {
            const active = pathname?.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold transition-colors ${
                  active ? 'bg-[var(--primary)] text-white' : 'text-gray-500 hover:bg-white/40'
                }`}
              >
                <Icon size={16} className="hidden sm:inline" /> {t(labelKey)}
              </Link>
            );
          })}
          <button
            onClick={() => setCode(code === 'en' ? 'ta' : 'en')}
            aria-label={t('language')}
            className="px-3 py-2 rounded-xl text-sm font-semibold text-gray-500 hover:bg-white/40 transition-colors"
          >
            {code === 'en' ? 'தமிழ்' : 'English'}
          </button>
          <button
            onClick={logout}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold text-red-500 hover:bg-red-500/10 transition-colors"
          >
            <LogOut size={16} /> <span className="hidden sm:inline">{t('logout')}</span>
          </button>
        </nav>
      </div>
    </header>
  );
}
