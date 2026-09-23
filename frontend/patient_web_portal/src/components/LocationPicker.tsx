"use client";

// Address search + map pin + "use my location", as one field.
//
// Leaflet touches `window` on import, so the map itself is behind a dynamic
// import with SSR off; everything else here renders server-side fine.

import React from 'react';
import dynamic from 'next/dynamic';
import { Crosshair, Loader2, MapPin, Search } from 'lucide-react';
import {
  geolocationErrorMessage,
  reverseGeocode,
  searchAddress,
  type PlaceSuggestion,
} from '../lib/geocode';
import type { LatLng } from './LocationPickerInner';

const LocationPickerInner = dynamic(() => import('./LocationPickerInner'), {
  ssr: false,
  loading: () => (
    <div className="h-[280px] w-full rounded-xl border border-white/20 animate-pulse bg-black/5 dark:bg-white/5" />
  ),
});

interface Props {
  address: string;
  lat: number | null;
  lng: number | null;
  onChange: (next: { address: string; lat: number | null; lng: number | null }) => void;
  label?: string;
  /** Shown under the field; the caller explains why coordinates matter. */
  hint?: string;
}

export default function LocationPicker({ address, lat, lng, onChange, label, hint }: Props) {
  const [suggestions, setSuggestions] = React.useState<PlaceSuggestion[]>([]);
  const [searching, setSearching] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const [locating, setLocating] = React.useState(false);
  const [notice, setNotice] = React.useState('');
  // Set while the address box is being filled from the map or GPS, so the
  // debounce below does not immediately search for the text it just wrote.
  const suppressNextSearch = React.useRef(false);
  const boxRef = React.useRef<HTMLDivElement>(null);

  const point: LatLng | null = lat != null && lng != null ? { lat, lng } : null;

  // Nominatim asks for no more than roughly one call a second. Debouncing
  // per keystroke is what keeps this inside that limit.
  React.useEffect(() => {
    if (suppressNextSearch.current) {
      suppressNextSearch.current = false;
      return;
    }
    const q = address.trim();
    if (q.length < 3) {
      setSuggestions([]);
      return;
    }
    const controller = new AbortController();
    setSearching(true);
    const timer = setTimeout(async () => {
      const found = await searchAddress(q, controller.signal);
      setSuggestions(found);
      setOpen(found.length > 0);
      setSearching(false);
    }, 700);
    return () => {
      clearTimeout(timer);
      controller.abort();
      setSearching(false);
    };
  }, [address]);

  // Clicking away closes the dropdown without choosing anything.
  React.useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const choose = (s: PlaceSuggestion) => {
    suppressNextSearch.current = true;
    setOpen(false);
    setSuggestions([]);
    setNotice('');
    onChange({ address: s.label, lat: s.lat, lng: s.lng });
  };

  /** Dropping or dragging the pin wins over whatever is typed: the point is
   *  what routing uses, so the written address is refreshed to match it. */
  const movePin = async (p: LatLng) => {
    setNotice('');
    onChange({ address, lat: p.lat, lng: p.lng });
    const found = await reverseGeocode(p.lat, p.lng);
    if (found) {
      suppressNextSearch.current = true;
      onChange({ address: found, lat: p.lat, lng: p.lng });
    }
  };

  const useMyLocation = () => {
    setNotice('');
    if (!navigator.geolocation) {
      setNotice('This browser cannot report a location. Drop the pin on the map instead.');
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setLocating(false);
        await movePin({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      (err) => {
        setLocating(false);
        // Previously this failed silently or with one vague line, leaving no
        // way to tell a blocked permission from a device with GPS off.
        setNotice(geolocationErrorMessage(err));
      },
      // Without a timeout the callback can simply never fire, which is what
      // "nothing happens when I click it" looked like.
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  };

  return (
    <div className="space-y-2">
      {label && <label className="block text-sm font-semibold">{label}</label>}

      <div ref={boxRef} className="relative">
        <div className="relative">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
          />
          <input
            type="text"
            value={address}
            onChange={(e) => onChange({ address: e.target.value, lat, lng })}
            onFocus={() => suggestions.length > 0 && setOpen(true)}
            placeholder="Start typing an address…"
            className="w-full pl-9 pr-9 p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-indigo-400 focus:outline-none"
          />
          {searching && (
            <Loader2 size={15} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-gray-400" />
          )}
        </div>

        {open && suggestions.length > 0 && (
          <ul className="absolute z-[1000] mt-1 w-full max-h-64 overflow-auto rounded-xl border border-white/20 bg-white dark:bg-neutral-900 shadow-xl">
            {suggestions.map((s, i) => (
              <li key={`${s.lat},${s.lng},${i}`}>
                <button
                  type="button"
                  onClick={() => choose(s)}
                  className="w-full text-left px-3 py-2.5 text-sm hover:bg-indigo-500/10 flex gap-2 items-start"
                >
                  <MapPin size={14} className="mt-0.5 shrink-0 text-indigo-500" />
                  <span>{s.label}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={useMyLocation}
          disabled={locating}
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-500 disabled:opacity-60"
        >
          {locating ? <Loader2 size={15} className="animate-spin" /> : <Crosshair size={15} />}
          {locating ? 'Finding your location…' : 'Use my current location'}
        </button>
        {point && (
          <span className="text-xs text-gray-500 tabular-nums">
            Pinned at {point.lat.toFixed(5)}, {point.lng.toFixed(5)}
          </span>
        )}
      </div>

      {notice && <p className="text-xs text-amber-600 dark:text-amber-400 font-medium">{notice}</p>}

      <LocationPickerInner value={point} onChange={movePin} />

      <p className="text-xs text-gray-500">
        {hint ?? 'Drag the pin or tap the map to set the exact spot.'}
      </p>
    </div>
  );
}
