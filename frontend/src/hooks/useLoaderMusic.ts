/**
 * useLoaderMusic — slot-aware audio playback for long-running loaders.
 *
 *   useLoaderMusic(enabled, slot?)  // slot defaults to 'default'
 *
 * Slots map to admin-uploaded audio files (Admin → Appearance → Loader music).
 * A slot with no upload falls back to the `default` slot automatically (the
 * server handles this). Admins can also mark a slot as explicitly silent.
 *
 * Per-user mute is persisted to AsyncStorage under `loaderMusicMuted` and
 * applies globally across every slot — the speaker icon on any loader can
 * flip it.
 */
import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from 'expo-audio';
import api from '../utils/api';

export type LoaderSlot = 'default' | 'deep_import' | 'url_import' | 'ai_assess_all' | 'mpps_pdf' | 'results_reveal';

const MUTE_KEY = 'loaderMusicMuted';

// Cached `/appearance` slots payload so 5 loaders don't all re-fetch.
let slotsCache: any = undefined;
let slotsPromise: Promise<any> | null = null;
async function getSlots(): Promise<any> {
  if (slotsCache !== undefined) return slotsCache;
  if (slotsPromise) return slotsPromise;
  slotsPromise = (async () => {
    try {
      const { data } = await api.get('/appearance');
      slotsCache = data?.loader_music_slots || {};
    } catch { slotsCache = {}; }
    return slotsCache;
  })();
  return slotsPromise;
}
export function invalidateLoaderMusicCache() {
  slotsCache = undefined; slotsPromise = null;
}

// Module-level mute pubsub so toggling on any loader updates every mounted one.
let mutedFlag = false;
const muteSubs = new Set<(v: boolean) => void>();
function setMuted(v: boolean) {
  mutedFlag = v;
  muteSubs.forEach((cb) => cb(v));
  AsyncStorage.setItem(MUTE_KEY, v ? '1' : '0').catch(() => { /* noop */ });
}
async function hydrateMute() {
  try {
    const v = await AsyncStorage.getItem(MUTE_KEY);
    if (v === '1') { mutedFlag = true; muteSubs.forEach((cb) => cb(true)); }
  } catch { /* noop */ }
}
hydrateMute();

export function useLoaderMusic(enabled: boolean, slot: LoaderSlot = 'default') {
  const [available, setAvailable] = useState(false);
  const [resolvedUrl, setResolvedUrl] = useState<string | null>(null);
  const [muted, setMutedState] = useState<boolean>(mutedFlag);

  // Subscribe to module-level mute changes.
  useEffect(() => {
    const cb = (v: boolean) => setMutedState(v);
    muteSubs.add(cb);
    return () => { muteSubs.delete(cb); };
  }, []);

  // Resolve slot URL (with auto-fallback to default on the server). The
  // hook checks the slots map locally too: if the slot is silenced AND
  // empty, we just no-op without even attempting to load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const slots = await getSlots();
      if (cancelled) return;
      const entry = slots?.[slot];
      const def = slots?.default;
      const slotSilent = entry?.silent === true;
      const hasAny = !!entry?.has || (!slotSilent && !!def?.has);
      if (!hasAny) {
        setAvailable(false); setResolvedUrl(null); return;
      }
      const base = (api.defaults.baseURL || '').replace(/\/api\/?$/, '');
      const v = entry?.has ? entry.version : (def?.version || 0);
      setResolvedUrl(`${base}/api/appearance/loader-music/${slot}?v=${v}`);
      setAvailable(true);
    })();
    return () => { cancelled = true; };
  }, [slot]);

  const source = useMemo(() => (resolvedUrl ? { uri: resolvedUrl } : null), [resolvedUrl]);
  const player = useAudioPlayer(source);
  const status = useAudioPlayerStatus(player);

  // Loop on completion.
  useEffect(() => {
    if (status?.didJustFinish && player) {
      try { player.seekTo(0); player.play(); } catch { /* noop */ }
    }
  }, [status?.didJustFinish, player]);

  // Respect prefers-reduced-motion on web.
  const reducedMotion =
    Platform.OS === 'web' && typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const effective = enabled && !muted && !reducedMotion;
  useEffect(() => {
    if (!player) return;
    let mounted = true;
    (async () => {
      try { await setAudioModeAsync({ playsInSilentMode: true }); } catch { /* noop */ }
      if (!mounted) return;
      if (effective) {
        try { player.volume = 0.55; } catch { /* noop */ }
        try { player.play(); } catch { /* autoplay blocked */ }
      } else {
        try { player.pause(); } catch { /* noop */ }
      }
    })();
    return () => { mounted = false; };
  }, [effective, player]);

  // Hard-stop on unmount.
  useEffect(() => () => { try { player?.pause(); } catch { /* noop */ } }, [player]);

  const toggleMute = useCallback(() => setMuted(!mutedFlag), []);

  return {
    available,
    playing: !!status?.playing,
    muted,
    toggleMute,
  };
}

export default useLoaderMusic;
