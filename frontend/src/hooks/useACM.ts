/**
 * useACM — Access Control Matrix hook
 * Fetches the user's access levels for all features from the backend.
 * Used by feature components to conditionally render/gate UI elements.
 *
 * Usage:
 *   const { access, checkFeature, isLoading } = useACM();
 *   const { allowed, access_level, quota_remaining } = checkFeature('my_dezider_create');
 *   if (access_level === 'hidden') return null;
 *   if (access_level === 'locked') return <UpgradePrompt />;
 */

import { useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const API = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL
  || process.env.EXPO_PUBLIC_BACKEND_URL
  || '';

interface FeatureAccess {
  access_level: string; // "full" | "read" | "locked" | "hidden" | "quota_exceeded"
  quota_limit: number;  // -1 = unlimited
  quota_used: number;
  quota_remaining: number; // -1 = unlimited
  quota_unit: string;   // e.g., "decisions/month", "toggle"
}

interface ACMState {
  user_type: string;
  subscription_plan: string;
  features: Record<string, FeatureAccess>;
}

const DEFAULT_ACCESS: FeatureAccess = {
  access_level: 'full',
  quota_limit: -1,
  quota_used: 0,
  quota_remaining: -1,
  quota_unit: 'toggle',
};

export function useACM() {
  const [state, setState] = useState<ACMState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAccess = useCallback(async () => {
    try {
      const token = await AsyncStorage.getItem('session_token');
      if (!token) {
        setIsLoading(false);
        return;
      }

      const resp = await fetch(`${API}/api/acm/my-access`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (resp.ok) {
        const data = await resp.json();
        setState(data);
        setError(null);
      } else {
        // If ACM not seeded yet, default to full access
        setError('ACM not available');
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAccess();
  }, [fetchAccess]);

  const checkFeature = useCallback(
    (featureId: string): FeatureAccess & { allowed: boolean } => {
      if (!state?.features) {
        // ACM not loaded → default to full access (backward compat)
        return { ...DEFAULT_ACCESS, allowed: true };
      }

      const feature = state.features[featureId];
      if (!feature) {
        return { ...DEFAULT_ACCESS, allowed: true };
      }

      const allowed =
        feature.access_level === 'full' ||
        feature.access_level === 'read';

      return { ...feature, allowed };
    },
    [state]
  );

  const isHidden = useCallback(
    (featureId: string): boolean => checkFeature(featureId).access_level === 'hidden',
    [checkFeature]
  );

  const isLocked = useCallback(
    (featureId: string): boolean => checkFeature(featureId).access_level === 'locked',
    [checkFeature]
  );

  const isReadOnly = useCallback(
    (featureId: string): boolean => checkFeature(featureId).access_level === 'read',
    [checkFeature]
  );

  const quotaExceeded = useCallback(
    (featureId: string): boolean => checkFeature(featureId).access_level === 'quota_exceeded',
    [checkFeature]
  );

  return {
    access: state,
    isLoading,
    error,
    checkFeature,
    isHidden,
    isLocked,
    isReadOnly,
    quotaExceeded,
    refresh: fetchAccess,
    userType: state?.user_type || 'free',
    subscriptionPlan: state?.subscription_plan || 'none',
  };
}
