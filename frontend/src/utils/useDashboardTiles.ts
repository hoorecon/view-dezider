/**
 * Dashboard tiles — single hook + helper for WOWO-controlled visibility.
 *
 * Pulls the user's ACM access map (/api/acm/my-access) once on mount and
 * exposes `isTileOn(tileId)` for each dashboard tile.
 *
 * Tile naming convention: `dash_<id>` (e.g. `dash_swot`, `dash_aala`).
 * The matching ACM features live under the `dashboard_tiles` module
 * (see backend/data/acm_seed_data.py).
 *
 * IMPORTANT — Wiring off a tile here only hides the *direct dashboard
 * entry*. Inter-module navigation (e.g. opening Goal Setter from inside
 * GEM) is NOT affected. This is by design: admin can declutter the home
 * screen without breaking embedded flows.
 *
 * Forward-compat: if `dash_<id>` is missing from the access map (e.g.
 * stale cache pre-seed), the tile is treated as ON.
 */
import { useEffect, useState, useCallback } from 'react';
import api from './api';

export interface TileAccess {
  // Backend `/api/acm/my-access` returns `access_level` (not `level`).
  // Keep both optional for forward compat with any callers using `level`.
  access_level?: 'full' | 'read' | 'locked' | 'hidden';
  level?: 'full' | 'read' | 'locked' | 'hidden';
  quota_limit?: number;
}

export interface UseDashboardTilesResult {
  loading: boolean;
  isTileOn: (tileId: string) => boolean;
  access: Record<string, TileAccess>;
  refresh: () => Promise<void>;
}

export function useDashboardTiles(): UseDashboardTilesResult {
  const [access, setAccess] = useState<Record<string, TileAccess>>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get('/acm/my-access');
      const features = r?.data?.features || {};
      // Keep only the dash_* feature flags — much smaller object to
      // re-render with.
      const dash: Record<string, TileAccess> = {};
      for (const k of Object.keys(features)) {
        if (k.startsWith('dash_')) dash[k] = features[k];
      }
      setAccess(dash);
    } catch (e) {
      // On error keep prior map — better to show stale tiles than hide all.
      console.warn('useDashboardTiles: failed to fetch /acm/my-access', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  /**
   * `dash_<id>` is ON when access level is full/read.
   * Missing key → ON (graceful default for forward compatibility).
   * Locked/hidden → OFF.
   */
  const isTileOn = useCallback((tileId: string): boolean => {
    const key = tileId.startsWith('dash_') ? tileId : `dash_${tileId}`;
    const a = access[key];
    if (!a) return true; // graceful default
    // Backend returns `access_level`; older shape used `level`. Accept both.
    const lvl = a.access_level ?? a.level;
    return lvl === 'full' || lvl === 'read';
  }, [access]);

  return { loading, isTileOn, access, refresh };
}
