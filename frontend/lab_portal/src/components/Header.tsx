"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FlaskConical, LayoutDashboard, BookOpen, UserCircle, LogOut } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const NAV = [
  { href: '/dashboard', label: 'Booking Queue', icon: LayoutDashboard },
  { href: '/catalog', label: 'Test Catalog', icon: BookOpen },
  { href: '/profile', label: 'Profile', icon: UserCircle },
];

export default function Header() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user || pathname === '/login' || pathname === '/onboarding') return null;

  return (
    <header className="sticky top-0 z-40 px-4 py-3 lg:px-8">
      <div className="glass-panel max-w-6xl mx-auto flex items-center justify-between px-5 py-3">
        <Link href="/dashboard" className="flex items-center gap-2 font-extrabold text-lg text-[var(--primary)]">
          <FlaskConical size={24} /> GramCare Lab
        </Link>
        <nav className="flex items-center gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname?.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold transition-colors ${
                  active ? 'bg-[var(--primary)] text-white' : 'text-gray-500 hover:bg-white/40'
                }`}
              >
                <Icon size={16} className="hidden sm:inline" /> {label}
              </Link>
            );
          })}
          <button
            onClick={logout}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold text-red-500 hover:bg-red-500/10 transition-colors"
          >
            <LogOut size={16} /> <span className="hidden sm:inline">Logout</span>
          </button>
        </nav>
      </div>
    </header>
  );
}
