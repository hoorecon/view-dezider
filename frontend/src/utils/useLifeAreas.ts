/**
 * useLifeAreas — single source of truth for Level-0 Life Areas across the app.
 *
 * Why this hook exists
 * --------------------
 * The Admin Central Catalog (HOS_SEED_DATA → `LIFE_AREAS`) is the canonical
 * list of 10 Level-0 life areas (Health, Knowledge, Relationships, Finance,
 * Career, Assets, Hobbies, Social Image, Social Contribution, Spirituality)
 * with admin-curated order, names, icons and colors.
 *
 * Before this hook, ~20 screens (Solution Finder, AIM Manager, Capabilities
 * Index, Goal Setter, Lifestyle Designer, SWOT, CTT, GEM, etc.) each
 * hardcoded their own L0 array with subtly different IDs/names/ordering.
 * That drift broke cross-module joins (a Solution Finder concern with
 * `life_area_id="career"` never matched a Capabilities row using
 * `life_area_id="la_career"`).
 *
 * Use this hook everywhere you need the L0 list.
 *
 * Returned items keep BOTH the canonical id and the legacy slug so migrating
 * screens can pass either to the backend during the transition.
 */
import { useEffect, useState, useCallback } from 'react';
import api from './api';

export interface LifeArea {
  /** Canonical id from Admin Central Catalog. Example: `la_career`. */
  id: string;
  /** Catalog node id (currently same as `id` for L0). */
  node_id: string;
  /** Display name. Example: `Career`. */
  name: string;
  /** Legacy short slug. Example: `career`. */
  slug: string;
  /** Ionicons name. */
  icon: string;
  /** Hex color. */
  color: string;
  /** Admin-curated display order (0-based ascending). */
  sort_order: number;
}

// Fallback used while the catalog endpoint is fetching, or if offline.
// Order MATCHES the Admin Central Catalog in `backend/data/hos_seed_data.py`.
const FALLBACK: LifeArea[] = [
  { id: 'la_health',        node_id: 'la_health',        name: 'Physical, Mental & Emotional Health', slug: 'holistic_health',       icon: 'fitness',          color: '#10B981', sort_order: 1 },
  { id: 'la_knowledge',     node_id: 'la_knowledge',     name: 'Knowledge & Skills',                  slug: 'knowledge_skills',      icon: 'book',             color: '#3B82F6', sort_order: 2 },
  { id: 'la_relationships', node_id: 'la_relationships', name: 'Relationships',                       slug: 'relationships',         icon: 'heart',            color: '#EC4899', sort_order: 3 },
  { id: 'la_finance',       node_id: 'la_finance',       name: 'Finance',                             slug: 'finance',               icon: 'cash',             color: '#F59E0B', sort_order: 4 },
  { id: 'la_career',        node_id: 'la_career',        name: 'Career',                              slug: 'career',                icon: 'briefcase',        color: '#6366F1', sort_order: 5 },
  { id: 'la_assets',        node_id: 'la_assets',        name: 'Assets (Movable & Immovable)',        slug: 'assets',                icon: 'home',             color: '#8B5CF6', sort_order: 6 },
  { id: 'la_hobbies',       node_id: 'la_hobbies',       name: 'Hobbies & Entertainment',             slug: 'hobbies_entertainment', icon: 'game-controller',  color: '#14B8A6', sort_order: 7 },
  { id: 'la_social_image',  node_id: 'la_social_image',  name: 'Social Image & Influence',            slug: 'social_image',          icon: 'star',             color: '#F97316', sort_order: 8 },
  { id: 'la_contribution',  node_id: 'la_contribution',  name: 'Social Contribution',                 slug: 'social_contributions',  icon: 'people',           color: '#06B6D4', sort_order: 9 },
  { id: 'la_spirituality',  node_id: 'la_spirituality',  name: 'Spirituality',                        slug: 'spirituality_religion', icon: 'leaf',             color: '#A855F7', sort_order: 10 },
];

// In-memory module cache — every call after the first paint is a no-op.
let _cache: LifeArea[] | null = null;
let _inFlight: Promise<LifeArea[]> | null = null;

async function _load(): Promise<LifeArea[]> {
  if (_cache) return _cache;
  if (_inFlight) return _inFlight;
  _inFlight = (async () => {
    try {
      const res = await api.get('/catalog/life-areas');
      const items: LifeArea[] = res.data?.items || [];
      if (items.length >= 1) {
        _cache = items;
        return items;
      }
    } catch {
      // fall through to fallback
    }
    _cache = FALLBACK;
    return FALLBACK;
  })();
  try {
    return await _inFlight;
  } finally {
    _inFlight = null;
  }
}

export interface UseLifeAreasResult {
  items: LifeArea[];
  loading: boolean;
  /** Look up by canonical id, legacy slug, or display name. Returns undefined if not found. */
  find: (key: string) => LifeArea | undefined;
  /** Force a re-fetch (e.g. after admin edits the catalog). */
  refresh: () => Promise<void>;
}

export function useLifeAreas(): UseLifeAreasResult {
  const [items, setItems] = useState<LifeArea[]>(() => _cache || FALLBACK);
  const [loading, setLoading] = useState<boolean>(() => !_cache);

  useEffect(() => {
    let alive = true;
    if (_cache) {
      setLoading(false);
      return;
    }
    _load().then((rows) => {
      if (alive) {
        setItems(rows);
        setLoading(false);
      }
    });
    return () => { alive = false; };
  }, []);

  const find = useCallback(
    (key: string): LifeArea | undefined => {
      if (!key) return undefined;
      const k = String(key).trim().toLowerCase();
      return items.find(
        (a) =>
          a.id.toLowerCase() === k
          || a.slug.toLowerCase() === k
          || a.node_id.toLowerCase() === k
          || a.name.toLowerCase() === k,
      );
    },
    [items],
  );

  const refresh = useCallback(async () => {
    _cache = null;
    setLoading(true);
    const rows = await _load();
    setItems(rows);
    setLoading(false);
  }, []);

  return { items, loading, find, refresh };
}
