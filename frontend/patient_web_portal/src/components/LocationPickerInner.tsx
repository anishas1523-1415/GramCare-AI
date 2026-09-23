"use client";

// Pick a point on a map: drag the pin, click the map, or use the device's
// own position. OpenStreetMap tiles, so there is no API key and no billing
// account involved.
//
// This exists because a hospital's coordinates are what SOS routing sorts
// on — a hospital saved without them is invisible to _nearest_hospital()'s
// distance sort and effectively never receives an emergency. Typing an
// address alone never produced coordinates, so getting them had to be
// possible without relying on the browser's location prompt succeeding.

import React from 'react';
import { MapContainer, TileLayer, Marker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export interface LatLng {
  lat: number;
  lng: number;
}

interface Props {
  value: LatLng | null;
  onChange: (point: LatLng) => void;
  /** Where to open when nothing is chosen yet. Defaults to Coimbatore. */
  fallbackCenter?: LatLng;
  heightClass?: string;
}

const DEFAULT_CENTER: LatLng = { lat: 11.0168, lng: 76.9558 };

// Leaflet's stock icons resolve by URL relative to its CSS, which a bundler
// breaks. Inline SVG avoids the 404 and keeps the pin legible in both themes.
const PIN = L.icon({
  iconUrl:
    'data:image/svg+xml;base64,' +
    btoa(`<svg xmlns="http://www.w3.org/2000/svg" width="30" height="44" viewBox="0 0 30 44">
      <path d="M15 0C6.7 0 0 6.7 0 15c0 10.8 13.4 27.1 14 27.8a1.3 1.3 0 0 0 2 0C16.6 42.1 30 25.8 30 15 30 6.7 23.3 0 15 0z" fill="#ef4444"/>
      <circle cx="15" cy="15" r="6" fill="#fff"/>
    </svg>`),
  iconSize: [30, 44],
  iconAnchor: [15, 44],
});

/** Keeps the view on the chosen point when it changes from outside the map
 *  (an address picked from the search dropdown, or the location button). */
function Recenter({ point }: { point: LatLng | null }) {
  const map = useMap();
  React.useEffect(() => {
    if (point) map.setView([point.lat, point.lng], Math.max(map.getZoom(), 15));
  }, [map, point]);
  return null;
}

/** Clicking anywhere on the map moves the pin there — the fastest way to
 *  correct a position that geocoding put slightly off. */
function ClickToPlace({ onChange }: { onChange: (p: LatLng) => void }) {
  useMapEvents({
    click(e) {
      onChange({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

export default function LocationPickerInner({
  value,
  onChange,
  fallbackCenter = DEFAULT_CENTER,
  heightClass = 'h-[280px]',
}: Props) {
  const center = value ?? fallbackCenter;

  return (
    <div className={`rounded-xl overflow-hidden border border-white/20 ${heightClass} w-full relative z-0`}>
      <MapContainer
        center={[center.lat, center.lng]}
        zoom={value ? 15 : 12}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <ClickToPlace onChange={onChange} />
        <Recenter point={value} />
        {value && (
          <Marker
            position={[value.lat, value.lng]}
            icon={PIN}
            draggable
            eventHandlers={{
              dragend: (e) => {
                const p = (e.target as L.Marker).getLatLng();
                onChange({ lat: p.lat, lng: p.lng });
              },
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}
