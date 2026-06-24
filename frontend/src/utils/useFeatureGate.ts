/**
 * Generic ACM feature gate.
 *
 * Fetches the user's ACM access map once (`/api/acm/my-access`) and exposes
 * `isOn(featureId)` for any feature_id (not just dashboard tiles). Used to
 * centrally show/hide collaboration affordances (Share, Expert Video call,
 * Shared Inbox) that the admin controls from the ACM → Collaboration module.
 *
 * Forward-compat: a missing feature defaults to ON, so new builds never hide
 * an affordance just because the ACM cache predates the feature.
 */
import { useEffect, useState, useCallback } from 'react';
import api from './api';

type Lvl = 'full' | 'read' | 'locked' | 'hidden';

export function useFeatureGate() {
  const [access, setAccess] = useState<Record<string, { access_level?: Lvl; level?: Lvl }>>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get('/acm/my-access');
      setAccess(r?.data?.features || {});
    } catch {
      // keep prior map — better to show than to hide everything on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const isOn = useCallback((featureId: string): boolean => {
    const a = access[featureId];
    if (!a) return true; // graceful default
    const lvl = a.access_level ?? a.level;
    return lvl === 'full' || lvl === 'read';
  }, [access]);

  return { loading, isOn, refresh };
}
