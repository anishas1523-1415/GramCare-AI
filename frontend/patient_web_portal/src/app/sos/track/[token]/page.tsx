"use client";

// The public side of an emergency — what a family member sees after tapping
// the link in their SMS.
//
// They are not users. Emergency contacts are phone numbers in a table, with
// no account to log into, so until this page existed the only thing an SOS
// could tell a relative was a map pin in a text message. This is the view
// they actually want: where the patient is, who is coming for them, how far
// off that is, and their own relative's voice.
//
// Unauthenticated by necessity, and deliberately narrow: no patient id, no
// medical history, no contact list. The token travels by SMS and may be
// forwarded to anyone.

import React from 'react';
import { use } from 'react';
import { HeartPulse, Hospital, MapPin, Phone, TriangleAlert } from 'lucide-react';
import LocationMap, { type MapPoint } from '../../../../components/LocationMap';
import api from '../../../../lib/api';

interface Tracking {
  patient_name: string;
  status: string;
  severity?: string | null;
  location_lat?: number | null;
  location_lng?: number | null;
  location_text?: string | null;
  voice_note?: string | null;
  voice_audio_url?: string | null;
  hospital_name?: string | null;
  hospital_phone?: string | null;
  hospital_lat?: number | null;
  hospital_lng?: number | null;
  distance_km?: number | null;
  eta_minutes?: number | null;
  eta_is_estimate: boolean;
  escalation_level: number;
  created_at: string;
  resolved_at?: string | null;
}

const STATUS_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  ACTIVE: {
    bg: 'bg-red-500/10 border-red-500/40',
    text: 'text-red-600',
    label: 'Waiting for a hospital to respond',
  },
  RESPONDED: {
    bg: 'bg-amber-500/10 border-amber-500/40',
    text: 'text-amber-600',
    label: 'Help is on the way',
  },
  RESOLVED: {
    bg: 'bg-emerald-500/10 border-emerald-500/40',
    text: 'text-emerald-600',
    label: 'This emergency has been resolved',
  },
};

function elapsed(from: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(from).getTime()) / 60000));
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs} h ${mins % 60} min ago`;
}

export default function SosTrackPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = React.useState<Tracking | null>(null);
  const [error, setError] = React.useState('');
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.get<Tracking>(`/sos/track/${token}`);
        if (!cancelled) {
          setData(res.data);
          setError('');
        }
      } catch {
        if (!cancelled) {
          setError('This tracking link is not valid, or the emergency has been removed.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    // An emergency changes underneath the reader: a hospital accepts it, it
    // escalates, the patient records a message. Polling keeps the page
    // honest without them having to refresh.
    const timer = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [token]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Loading…</div>;
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="glass-panel max-w-md w-full p-8 text-center">
          <TriangleAlert size={40} className="text-red-500 mx-auto mb-4" />
          <p className="text-gray-500">{error}</p>
        </div>
      </div>
    );
  }

  const style = STATUS_STYLE[data.status] ?? STATUS_STYLE.ACTIVE;
  const points: MapPoint[] = [];
  if (data.location_lat != null && data.location_lng != null) {
    points.push({
      id: 'patient',
      lat: data.location_lat,
      lng: data.location_lng,
      label: `${data.patient_name} — emergency location`,
      highlight: true,
    });
  }
  if (data.hospital_lat != null && data.hospital_lng != null) {
    points.push({
      id: 'hospital',
      lat: data.hospital_lat,
      lng: data.hospital_lng,
      label: data.hospital_name ?? 'Responding hospital',
    });
  }

  return (
    <div className="min-h-screen p-4 sm:p-6 flex justify-center">
      <div className="w-full max-w-lg">
        <div className={`glass-panel border-2 ${style.bg} p-5 mb-4`}>
          <p className="text-xs font-bold uppercase tracking-wider text-red-500 mb-1">
            GramCare AI · Emergency
          </p>
          <h1 className="text-2xl font-extrabold">{data.patient_name}</h1>
          <p className={`text-sm font-bold mt-1 ${style.text}`}>{style.label}</p>
          <p className="text-xs text-gray-500 mt-1">
            Alerted {elapsed(data.created_at)}
            {data.escalation_level > 0 && ` · escalated ${data.escalation_level}×`}
          </p>
        </div>

        {points.length > 0 && <LocationMap points={points} borderClass="border-red-500/40" />}

        {/* Distance and ETA are what a relative asks first. The estimate is
            labelled as one rather than dressed up as a road time, because
            someone is deciding whether to set off themselves. */}
        {data.hospital_name && (
          <div className="glass-panel p-4 mb-4">
            <p className="text-sm font-bold flex items-center gap-2 mb-2">
              <Hospital size={16} className="text-indigo-500" /> {data.hospital_name}
            </p>
            {data.distance_km != null && (
              <div className="flex gap-6">
                <div>
                  <p className="text-xs text-gray-500 font-semibold">Distance</p>
                  <p className="text-xl font-extrabold tabular-nums">{data.distance_km} km</p>
                </div>
                {data.eta_minutes != null && (
                  <div>
                    <p className="text-xs text-gray-500 font-semibold">
                      {data.eta_is_estimate ? 'Estimated arrival' : 'Arrival'}
                    </p>
                    <p className="text-xl font-extrabold tabular-nums">~{data.eta_minutes} min</p>
                  </div>
                )}
              </div>
            )}
            {data.eta_is_estimate && data.distance_km != null && (
              <p className="text-xs text-gray-500 mt-2">
                Estimated from straight-line distance, not a live road route.
              </p>
            )}
            {data.hospital_phone && (
              <a
                href={`tel:${data.hospital_phone}`}
                className="mt-3 inline-flex items-center gap-2 text-indigo-500 font-semibold text-sm"
              >
                <Phone size={15} /> Call {data.hospital_phone}
              </a>
            )}
          </div>
        )}

        {data.location_text && (
          <div className="glass-panel p-4 mb-4">
            <p className="text-sm font-bold flex items-center gap-2 mb-1">
              <MapPin size={16} className="text-red-500" /> Location
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-300">{data.location_text}</p>
          </div>
        )}

        {(data.voice_audio_url || data.voice_note) && (
          <div className="glass-panel p-4 mb-4">
            <p className="text-sm font-bold flex items-center gap-2 mb-2">
              <HeartPulse size={16} className="text-teal-500" /> What they said
            </p>
            {data.voice_audio_url && (
              <audio controls preload="none" src={data.voice_audio_url} className="w-full h-9 mb-2" />
            )}
            {data.voice_note && (
              <p className="text-sm italic text-gray-600 dark:text-gray-300">
                &ldquo;{data.voice_note}&rdquo;
              </p>
            )}
          </div>
        )}

        <p className="text-xs text-center text-gray-400 mt-6">
          This page updates automatically. In a life-threatening emergency, call 108.
        </p>
      </div>
    </div>
  );
}
