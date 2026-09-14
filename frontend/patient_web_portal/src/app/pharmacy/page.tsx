"use client";

// Nearby medicine availability — the planning doc's pharmacy search:
// green = in stock nearby, red = unavailable (with generic substitutes
// suggested at that shop). Uses browser geolocation when granted;
// works ungated without it (results just aren't distance-ranked).

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Pill, Search, MapPin, Phone, CheckCircle2, XCircle, Landmark, PackagePlus } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';
import { useLocale } from '../../contexts/LocaleContext';
import type { NearbyPharmacyResult } from '../../types';
import LocationMap from '../../components/LocationMap';
import { SkeletonList } from '../../components/Skeleton';

export default function PharmacySearch() {
  const { user } = useAuth();
  const { t } = useLocale();
  const [medicine, setMedicine] = useState('');
  const [results, setResults] = useState<NearbyPharmacyResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [usedLocation, setUsedLocation] = useState(false);
  const [preorderedIds, setPreorderedIds] = useState<Set<number>>(new Set());

  const preorder = async (pharmacyId: number, medicineName: string) => {
    try {
      await api.post('/pharmacy/preorders', {
        pharmacy_id: pharmacyId,
        medicine_name: medicineName,
        quantity: 1,
      });
      setPreorderedIds((prev) => new Set(prev).add(pharmacyId));
    } catch {
      setError(t('preorder_failed'));
    }
  };

  const search = async () => {
    if (medicine.trim().length < 2) return;
    setLoading(true);
    setError('');
    setResults(null);

    let lat: number | undefined;
    let lng: number | undefined;
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 6000 }));
      lat = pos.coords.latitude;
      lng = pos.coords.longitude;
      setUsedLocation(true);
    } catch {
      setUsedLocation(false); // denied/unavailable — search without distance
    }

    try {
      const res = await api.get<NearbyPharmacyResult[]>('/pharmacy/search', {
        params: { medicine: medicine.trim(), lat, lng },
      });
      setResults(res.data);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(status === 401
        ? t('please_login_pharmacy_search')
        : t('pharmacy_search_failed'));
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">{t('please_login_find_medicines')}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 lg:p-24">
      {/* Pharmacy module theme: green (planning doc's per-module color identity) */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
        <div className="absolute top-[10%] right-[15%] w-96 h-96 bg-emerald-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 dark:opacity-40" />
      </div>

      <div className="max-w-3xl mx-auto">
        <h1 className="text-4xl font-extrabold flex items-center gap-3 mb-2">
          <Pill className="text-emerald-500" size={40} /> {t('nav_find_medicine')}
        </h1>
        <p className="text-gray-500 mb-8">
          {t('find_medicine_subtitle')}
        </p>

        <div className="flex gap-3 mb-8">
          <input
            type="text"
            value={medicine}
            onChange={(e) => setMedicine(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
            placeholder={t('medicine_name_hint')}
            aria-label="Medicine name"
            className="flex-1 p-4 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:ring-2 focus:ring-emerald-400 outline-none"
          />
          <button
            onClick={search}
            disabled={loading || medicine.trim().length < 2}
            className="neu-button px-6 bg-emerald-500 text-white font-bold rounded-xl flex items-center gap-2 disabled:opacity-40"
          >
            <Search size={18} /> {loading ? t('searching_ellipsis') : t('search_button')}
          </button>
        </div>

        {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

        {loading && <SkeletonList count={3} />}

        {!loading && results !== null && (
          <>
            <p className="text-sm text-gray-500 mb-4">
              {usedLocation ? t('sorted_by_distance') : t('location_off_all_pharmacies')}
            </p>
            {results.length === 0 ? (
              <div className="glass-panel p-10 text-center text-gray-500">
                {t('no_pharmacies_found')}
              </div>
            ) : (
              <div className="space-y-4">
                <LocationMap
                  mapId="pharmacy_map"
                  borderClass="border-emerald-500/30"
                  points={results
                    .filter((r) => r.lat != null && r.lng != null)
                    .map((r) => ({
                      id: r.pharmacy_id,
                      lat: r.lat!,
                      lng: r.lng!,
                      label: r.pharmacy_name,
                      highlight: !r.available,
                    }))}
                />
                {results.map((r) => (
                  <motion.div
                    key={r.pharmacy_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`glass-panel p-5 border-l-8 ${r.available ? 'border-l-emerald-500' : 'border-l-red-400'}`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="font-bold text-lg flex items-center gap-2">
                          {r.pharmacy_name}
                          {r.is_jan_aushadhi && (
                            <span className="flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-600">
                              <Landmark size={12} /> {t('jan_aushadhi')}
                            </span>
                          )}
                        </h3>
                        <p className="text-sm text-gray-500 flex items-center gap-1">
                          <MapPin size={14} /> {r.address || 'Address not listed'}
                          {r.distance_km != null && <span className="font-semibold"> · {r.distance_km} km</span>}
                        </p>
                        {r.phone && (
                          <a href={`tel:${r.phone}`} className="text-sm text-emerald-600 flex items-center gap-1 mt-1">
                            <Phone size={14} /> {r.phone}
                          </a>
                        )}
                      </div>
                      <div className="text-right">
                        {r.available ? (
                          <span className="flex items-center gap-1 text-emerald-600 font-bold">
                            <CheckCircle2 size={18} /> {t('in_stock')}
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-red-500 font-bold">
                            <XCircle size={18} /> {t('not_available')}
                          </span>
                        )}
                        {r.available && r.price != null && (
                          <div className="text-sm text-gray-500 mt-1">₹{r.price.toFixed(2)}</div>
                        )}
                      </div>
                    </div>

                    {!r.available && r.substitutes.length > 0 && (
                      <div className="mt-3 p-3 rounded-xl bg-emerald-500/10 text-sm">
                        <span className="font-bold text-emerald-700">{t('alternatives')}: </span>
                        {r.substitutes.join(', ')}
                      </div>
                    )}

                    {!r.available && (
                      <button
                        onClick={() => preorder(r.pharmacy_id, medicine.trim())}
                        disabled={preorderedIds.has(r.pharmacy_id)}
                        className="mt-3 w-full py-2 rounded-xl border border-indigo-400 text-indigo-500 font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-50 disabled:border-gray-300 disabled:text-gray-400 hover:bg-indigo-500/10 transition-colors"
                      >
                        <PackagePlus size={16} />
                        {preorderedIds.has(r.pharmacy_id) ? t('preordered_notify') : t('preorder_cta')}
                      </button>
                    )}
                  </motion.div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
