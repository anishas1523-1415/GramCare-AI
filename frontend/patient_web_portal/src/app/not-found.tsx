"use client";

import Link from "next/link";
import { MapPinOff, Home } from "lucide-react";
import { useLocale } from "../contexts/LocaleContext";

export default function NotFound() {
  const { t } = useLocale();

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="glass-panel max-w-md w-full p-8 text-center">
        <MapPinOff className="mx-auto mb-4 text-indigo-400" size={48} />
        <h1 className="text-xl font-bold mb-2">{t('page_not_found')}</h1>
        <p className="text-gray-500 text-sm mb-6">{t('not_found_body')}</p>
        <Link
          href="/"
          className="neu-button inline-flex items-center justify-center gap-2 py-3 px-6 bg-indigo-500 text-white font-bold rounded-xl"
        >
          <Home size={16} /> {t('back_to_home')}
        </Link>
      </div>
    </div>
  );
}
