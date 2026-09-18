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

let _acmMemoryCache: ACMState | null = null;
let _acmInflight: Promise<ACMState | null> | null = null;

export function useACM() {
  const [state, setState] = useState<ACMState | null>(_acmMemoryCache);
  const [isLoading, setIsLoading] = useState(!_acmMemoryCache);
  const [error, setError] = useState<string | null>(null);

  const fetchAccess = useCallback(async () => {
    try {
      const token = await AsyncStorage.getItem('session_token');
      if (!token) {
        setIsLoading(false);
        return;
      }

      if (_acmInflight) {
        const data = await _acmInflight;
        if (data) {
          setState(data);
          setIsLoading(false);
        }
        return;
      }

      _acmInflight = fetch(`${API}/api/acm/my-access`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }).then(async (resp) => {
        _acmInflight = null;
        if (resp.ok) {
          const data = await resp.json();
          _acmMemoryCache = data;
          return data;
        }
        return null;
      }).catch(() => {
        _acmInflight = null;
        return null;
      });

      const data = await _acmInflight;
      if (data) {
        setState(data);
        setError(null);
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

      const allowed = feature.access_level === 'full';
      const canRead = feature.access_level === 'full' || feature.access_level === 'read';

      return { ...feature, allowed, canRead };
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

export function isSubscriptionUserOrAdmin(state: ACMState | null): boolean {
  if (!state) return false;
  const plan = (state.subscription_plan || '').toLowerCase().trim();
  const utype = (state.user_type || '').toLowerCase().trim();

  // Active subscription plan (basic, pro, premium, enterprise, starter)
  const isSubscribedPlan = plan !== '' && plan !== 'none' && plan !== 'free';

  // Admin or test tier bypass
  const adminOrTesterTypes = [
    'admin', 'super_admin', 'co_admin',
    'alpha', 'beta', 'unit_tester', 'integration_tester'
  ];
  const isAdminOrTester = adminOrTesterTypes.includes(utype);

  return isSubscribedPlan || isAdminOrTester;
}

export function useIsSubscriptionUserOrAdmin(): boolean {
  const { access, isLoading } = useACM();
  const targetState = access || _acmMemoryCache;
  if (!targetState && isLoading) return false;
  return isSubscriptionUserOrAdmin(targetState);
}
