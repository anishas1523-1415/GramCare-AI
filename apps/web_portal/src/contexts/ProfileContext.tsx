"use client";

/**
 * Active family-profile context — the planning doc's rule that the user
 * first selects WHICH family member they are acting for, and every feature
 * (triage, records, booking, vitals) is then scoped to that member.
 * `null` means "the account owner themself".
 *
 * The selection is persisted per-user in localStorage so it survives
 * reloads (matching the mobile app's persisted selection).
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import api from '../lib/api';
import { useAuth } from './AuthContext';
import type { FamilyProfile } from '../types';

interface ProfileContextType {
  profiles: FamilyProfile[];
  activeProfile: FamilyProfile | null; // null = account owner
  setActiveProfile: (p: FamilyProfile | null) => void;
  refreshProfiles: () => Promise<void>;
  loading: boolean;
}

const ProfileContext = createContext<ProfileContextType>({
  profiles: [],
  activeProfile: null,
  setActiveProfile: () => {},
  refreshProfiles: async () => {},
  loading: false,
});

const storageKey = (userId: number) => `gramcare_active_profile_${userId}`;

export const ProfileProvider = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuth();
  const [profiles, setProfiles] = useState<FamilyProfile[]>([]);
  const [activeProfile, setActiveProfileState] = useState<FamilyProfile | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshProfiles = useCallback(async () => {
    if (!user) {
      setProfiles([]);
      setActiveProfileState(null);
      return;
    }
    setLoading(true);
    try {
      const res = await api.get<FamilyProfile[]>('/family');
      setProfiles(res.data);

      // Restore the persisted selection if it still exists
      const savedId = localStorage.getItem(storageKey(user.id!));
      if (savedId) {
        const saved = res.data.find((p) => p.id === Number(savedId)) || null;
        setActiveProfileState(saved);
      }
    } catch (err) {
      console.error('Failed to load family profiles:', err);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    refreshProfiles();
  }, [refreshProfiles]);

  const setActiveProfile = (p: FamilyProfile | null) => {
    setActiveProfileState(p);
    if (user) {
      if (p) localStorage.setItem(storageKey(user.id!), String(p.id));
      else localStorage.removeItem(storageKey(user.id!));
    }
  };

  return (
    <ProfileContext.Provider
      value={{ profiles, activeProfile, setActiveProfile, refreshProfiles, loading }}
    >
      {children}
    </ProfileContext.Provider>
  );
};

export const useProfile = () => useContext(ProfileContext);
