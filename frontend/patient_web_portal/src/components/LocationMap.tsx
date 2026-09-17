"use client";

// Leaflet reaches for `window` as soon as it is imported, which crashes the
// server render. Next only guarantees a browser for a dynamic import with
// ssr disabled, so the real map lives in LocationMapInner and this wrapper
// is all any page imports.

import dynamic from 'next/dynamic';
import React from 'react';

export type { MapPoint } from './LocationMapInner';

const LocationMap = dynamic(() => import('./LocationMapInner'), {
  ssr: false,
  loading: () => (
    <div className="mb-6 rounded-2xl border border-white/10 h-[300px] w-full animate-pulse bg-black/5 dark:bg-white/5" />
  ),
});

export default LocationMap;
