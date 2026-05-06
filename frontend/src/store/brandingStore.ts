/**
 * brandingStore.ts — Hydrates active edition's brand surface on app boot.
 *
 * Powered by GET /api/branding/current. Cached in AsyncStorage so the splash
 * screen can render correct branding before the network call returns.
 *
 * Editions today:
 *   • jelcos      — JELCOS AI (Business Leaders)
 *   • geodezider  — GeoDezider AI (Govt)
 *   • consumer    — Earth Dezider (future consumer edition)
 */
import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../utils/api';

export interface BrandConfig {
  edition: 'jelcos' | 'geodezider' | 'consumer';
  display_name: string;
  full_expansion: string;
  tagline: string;
  audience_identity: string;
  primary_color: string;
  secondary_color: string;
  logo_uri: string | null;
  domain: string | null;
  audience_segments: string[];
  enabled_features: string[];
  master_brand: string;
  master_tagline: string;
  legal_entity: string;
}

const FALLBACK: BrandConfig = {
  edition: 'jelcos',
  display_name: 'JELCOS AI',
  full_expansion: "Joyful Executive's Life Choices Operating System powered by Artificial Intelligence",
  tagline: "The AI Decision OS for the Joyful Executive's life.",
  audience_identity: 'The Joyful Executive',
  primary_color: '#7C3AED',
  secondary_color: '#1A237E',
  logo_uri: null,
  domain: 'jelcos.ai',
  audience_segments: ['Solopreneurs', 'Startup Founders', 'MSME Founders', 'CXOs', 'Corporate Managers'],
  enabled_features: [],
  master_brand: 'Earth Dezider',
  master_tagline: 'The Decision OS for People.',
  legal_entity: 'VEALES Vedic Decisions Private Limited',
};

const CACHE_KEY = 'branding_cache_v1';

interface BrandingState {
  brand: BrandConfig;
  loaded: boolean;
  loading: boolean;
  error: string | null;
  hydrate: () => Promise<void>;
  reload: () => Promise<void>;
  isFeatureEnabled: (key: string) => boolean;
}

export const useBrandingStore = create<BrandingState>((set, get) => ({
  brand: FALLBACK,
  loaded: false,
  loading: false,
  error: null,

  hydrate: async () => {
    if (get().loaded || get().loading) return;
    set({ loading: true });

    // Step 1: serve cached value instantly so splash isn't blank
    try {
      const cached = await AsyncStorage.getItem(CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached) as BrandConfig;
        set({ brand: parsed, loaded: true });
      }
    } catch { /* ignore cache miss */ }

    // Step 2: fetch fresh from server in background
    try {
      const r = await api.get('/branding/current');
      const fresh = r.data?.branding as BrandConfig;
      if (fresh) {
        set({ brand: fresh, loaded: true, loading: false, error: null });
        await AsyncStorage.setItem(CACHE_KEY, JSON.stringify(fresh));
      } else {
        set({ loaded: true, loading: false });
      }
    } catch (e: any) {
      // Network down? Fall back to cached or hard-coded default.
      set({ loaded: true, loading: false, error: e?.message || 'branding fetch failed' });
    }
  },

  reload: async () => {
    set({ loaded: false, loading: false });
    await get().hydrate();
  },

  isFeatureEnabled: (key: string) => {
    const list = get().brand.enabled_features || [];
    return list.length === 0 || list.includes(key);
  },
}));
