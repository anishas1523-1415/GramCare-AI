"use client";

// Shared map surface for the two places that plot coordinates (nearby
// pharmacies, active SOS calls).
//
// @vis.gl/react-google-maps renders an unusable grey box when handed an
// empty apiKey, and Google itself renders a dark "this page didn't load
// Google Maps correctly" box when the key is present but rejected —
// which is what production has been showing, because the deployed key has
// no billing account attached. Both cases fall back to a list of the same
// points as Google Maps deep links: those need no API key, open the real
// map, and on a phone hand off to the Maps app with directions, which is
// what a rural user actually needs from "where is this pharmacy".

import React from 'react';
import { MapPin, ExternalLink } from 'lucide-react';
import { APIProvider, Map, Marker } from '@vis.gl/react-google-maps';
import { useLocale } from '../contexts/LocaleContext';

export interface MapPoint {
  id: string | number;
  lat: number;
  lng: number;
  label: string;
  /** Renders the marker in the "attention" colour (unavailable stock, active SOS). */
  highlight?: boolean;
}

interface Props {
  points: MapPoint[];
  mapId: string;
  /** Tailwind border colour class, so each module keeps its own accent. */
  borderClass?: string;
}

// Google calls this global when it rejects the key — expired, restricted
// away from this origin, or (our case) no billing account. There is no
// React-level event for it, and it fires after the script has loaded
// successfully, so APIProvider's onError never sees it.
declare global {
  interface Window {
    gm_authFailure?: () => void;
  }
}

function MapLinkList({
  points,
  borderClass,
  note,
  openLabel,
}: {
  points: MapPoint[];
  borderClass: string;
  note: string;
  openLabel: string;
}) {
  return (
    <div className={`mb-6 rounded-2xl border ${borderClass} overflow-hidden`}>
      <div className="px-4 py-2 text-xs font-semibold text-gray-500 border-b border-white/10 flex items-center gap-1.5">
        <MapPin size={13} /> {note}
      </div>
      <ul className="divide-y divide-white/10">
        {points.map((p) => (
          <li key={p.id}>
            <a
              href={`https://maps.google.com/?q=${p.lat},${p.lng}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-white/5 transition-colors"
            >
              <span className="flex items-center gap-2 min-w-0">
                <span
                  aria-hidden
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${p.highlight ? 'bg-red-500' : 'bg-emerald-500'}`}
                />
                <span className="truncate font-semibold">{p.label}</span>
              </span>
              <span className="flex items-center gap-1 text-indigo-500 font-semibold shrink-0">
                {openLabel} <ExternalLink size={13} />
              </span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function LocationMap({ points, mapId, borderClass = 'border-emerald-500/30' }: Props) {
  const { t } = useLocale();
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
  const [keyRejected, setKeyRejected] = React.useState(false);
  const plottable = points.filter((p) => p.lat != null && p.lng != null);

  React.useEffect(() => {
    if (!apiKey) return;
    const previous = window.gm_authFailure;
    window.gm_authFailure = () => {
      setKeyRejected(true);
      previous?.();
    };
    return () => {
      window.gm_authFailure = previous;
    };
  }, [apiKey]);

  if (plottable.length === 0) return null;

  if (!apiKey || keyRejected) {
    return (
      <MapLinkList
        points={plottable}
        borderClass={borderClass}
        note={t('map_unavailable_note')}
        openLabel={t('open_in_maps')}
      />
    );
  }

  return (
    <div className={`mb-6 rounded-2xl overflow-hidden border ${borderClass} h-[300px] w-full`}>
      <APIProvider apiKey={apiKey} onError={() => setKeyRejected(true)}>
        <Map
          defaultZoom={12}
          defaultCenter={{ lat: plottable[0].lat, lng: plottable[0].lng }}
          mapId={mapId}
          gestureHandling="greedy"
          disableDefaultUI
        >
          {plottable.map((p) => (
            <Marker
              key={`marker-${p.id}`}
              position={{ lat: p.lat, lng: p.lng }}
              title={p.label}
              icon={p.highlight
                ? 'https://maps.google.com/mapfiles/ms/icons/red-dot.png'
                : 'https://maps.google.com/mapfiles/ms/icons/green-dot.png'}
            />
          ))}
        </Map>
      </APIProvider>
    </div>
  );
}
