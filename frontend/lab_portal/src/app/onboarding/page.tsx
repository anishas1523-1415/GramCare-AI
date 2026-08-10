"use client";

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { MapPin, Building2 } from 'lucide-react';
import api from '../../lib/api';
import { useAuth } from '../../contexts/AuthContext';

export default function OnboardingPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [lat, setLat] = useState<string>('');
  const [lng, setLng] = useState<string>('');
  const [homeCollection, setHomeCollection] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!loading && !user) {
    router.replace('/login');
  }

  const useMyLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude.toFixed(6));
        setLng(pos.coords.longitude.toFixed(6));
      },
      () => setError('Could not access location — enter it manually or skip.'),
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await api.post('/lab/register', {
        name,
        address: address || undefined,
        phone: phone || undefined,
        lat: lat ? parseFloat(lat) : undefined,
        lng: lng ? parseFloat(lng) : undefined,
        offers_home_collection: homeCollection,
      });
      router.push('/dashboard');
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Could not save your lab profile. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel w-full max-w-lg p-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <Building2 size={32} className="text-[var(--primary)]" />
          <h1 className="text-2xl font-bold">Set Up Your Lab</h1>
        </div>
        <p className="text-gray-500 mb-6">
          One-time setup so patients can find and book tests at your center.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-semibold mb-2">Lab Name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold mb-2">Address</label>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold mb-2">Phone</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold mb-2">Latitude</label>
              <input
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                inputMode="decimal"
                className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold mb-2">Longitude</label>
              <input
                value={lng}
                onChange={(e) => setLng(e.target.value)}
                inputMode="decimal"
                className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20 focus:ring-2 focus:ring-[var(--primary)] focus:outline-none"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={useMyLocation}
            className="text-sm font-semibold text-[var(--primary)] flex items-center gap-1"
          >
            <MapPin size={14} /> Use my current location
          </button>

          <label className="flex items-center gap-3 p-3 rounded-xl bg-white/40 dark:bg-black/20 cursor-pointer">
            <input
              type="checkbox"
              checked={homeCollection}
              onChange={(e) => setHomeCollection(e.target.checked)}
              className="w-5 h-5 accent-[var(--primary)]"
            />
            <span className="font-semibold text-sm">We offer home sample collection</span>
          </label>

          {error && <p role="alert" className="text-red-500 text-sm font-semibold text-center">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="neu-button w-full py-3 bg-[var(--primary)] text-white font-bold rounded-xl disabled:opacity-50"
          >
            {submitting ? 'Saving…' : 'Save & Continue'}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
