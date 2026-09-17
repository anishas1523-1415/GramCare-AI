"use client";

// Shared map surface for every place that plots coordinates (nearby
// pharmacies, active SOS calls, hospitals, doctors).
//
// This used to be Google Maps, which needs an API key attached to a billing
// account. The deployed key had none, so Google loaded, rejected it, and
// painted its own "this page didn't load Google Maps correctly" box — the
// map was blank on every surface, in production, for everyone. Falling back
// to a list of links hid the error but still left users with no map.
//
// OpenStreetMap needs no key, no billing and no account, so the map simply
// works. Tiles come straight from the OSM tile servers; the attribution
// below is required by their tile usage policy.

import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
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
  /** Kept for call-site compatibility with the previous Google implementation. */
  mapId?: string;
  /** Tailwind border colour class, so each module keeps its own accent. */
  borderClass?: string;
  heightClass?: string;
}

// Leaflet's default marker icons are loaded by URL relative to the CSS,
// which breaks under a bundler. Drawing them as inline SVG data URIs keeps
// the pin colours meaningful (red = needs attention) and avoids the 404s
// the default icons would otherwise produce.
function pin(color: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="38" viewBox="0 0 26 38">
    <path d="M13 0C5.8 0 0 5.8 0 13c0 9.4 11.6 23.4 12.1 24a1.2 1.2 0 0 0 1.8 0C14.4 36.4 26 22.4 26 13 26 5.8 20.2 0 13 0z" fill="${color}"/>
    <circle cx="13" cy="13" r="5" fill="#fff"/>
  </svg>`;
  return L.icon({
    iconUrl: `data:image/svg+xml;base64,${btoa(svg)}`,
    iconSize: [26, 38],
    iconAnchor: [13, 38],
    popupAnchor: [0, -34],
  });
}

/** Frames every point, so the map opens zoomed to the data rather than at
 *  an arbitrary default the user has to pan around to find. */
function FitToPoints({ points }: { points: MapPoint[] }) {
  const map = useMap();
  React.useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView([points[0].lat, points[0].lng], 15);
      return;
    }
    map.fitBounds(L.latLngBounds(points.map((p) => [p.lat, p.lng] as [number, number])), {
      padding: [40, 40],
      maxZoom: 16,
    });
  }, [map, points]);
  return null;
}

export default function LocationMap({
  points,
  borderClass = 'border-emerald-500/30',
  heightClass = 'h-[300px]',
}: Props) {
  const { t } = useLocale();
  const plottable = points.filter((p) => p.lat != null && p.lng != null);

  if (plottable.length === 0) return null;

  return (
    <div className={`mb-6 rounded-2xl overflow-hidden border ${borderClass} ${heightClass} w-full relative z-0`}>
      <MapContainer
        center={[plottable[0].lat, plottable[0].lng]}
        zoom={14}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <FitToPoints points={plottable} />
        {plottable.map((p) => (
          <Marker
            key={p.id}
            position={[p.lat, p.lng]}
            icon={pin(p.highlight ? '#ef4444' : '#10b981')}
          >
            <Popup>
              <span className="font-semibold">{p.label}</span>
              <br />
              <a
                href={`https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lng}#map=17/${p.lat}/${p.lng}`}
                target="_blank"
                rel="noreferrer"
              >
                {t('open_in_maps')}
              </a>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
