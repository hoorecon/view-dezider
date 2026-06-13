/**
 * useLoaderMusic — plays an admin-uploaded audio file in a loop while a UI
 * loader is running (Deep Import, long crawls). Resolves the URL once from
 * `/api/appearance` and starts/stops based on the `enabled` flag.
 *
 * Cross-platform: uses `expo-audio` (which wraps the Web Audio API on web).
 *
 * Caller usage:
 *   useLoaderMusic(stage === 'crawling' || stage === 'merging');
 *
 * Caveats:
 *  - On web, browsers BLOCK autoplay until the user has interacted with the
 *    page. Since the Deep-Import flow starts with the user CLICKING "Run
 *    crawl", that interaction unblocks audio — calling `player.play()` from
 *    inside the click handler is enough.
 *  - When no music is uploaded the hook silently no-ops; users get the same
 *    progress experience minus the soundtrack.
 *  - Honours `prefers-reduced-motion` / `reduced-motion` on web by NOT
 *    auto-starting; the user can still enable manually via the loader's
 *    speaker icon if we surface one in future.
 */
import { useEffect, useMemo, useRef } from 'react';
import { Platform } from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from 'expo-audio';
import api from '../utils/api';

let cachedUrl: string | null | undefined = undefined;  // first-fetch memo
let cachedPromise: Promise<string | null> | null = null;

async function resolveLoaderMusicUrl(): Promise<string | null> {
  if (cachedUrl !== undefined) return cachedUrl;
  if (cachedPromise) return cachedPromise;
  cachedPromise = (async () => {
    try {
      const { data } = await api.get('/appearance');
      if (data?.loader_music_url) {
        // Absolute URL: appearance returns a path; resolve against API base.
        const base = (api.defaults.baseURL || '').replace(/\/api\/?$/, '');
        // cache-bust on version so removing + re-uploading flushes the buffer
        const v = data.loader_music_version || 0;
        const u = `${base}${data.loader_music_url}?v=${v}`;
        cachedUrl = u;
      } else {
        cachedUrl = null;
      }
    } catch {
      cachedUrl = null;
    }
    return cachedUrl ?? null;
  })();
  return cachedPromise;
}

/** Call once with a URL to manually invalidate the cache (e.g. after a new
 *  upload from /admin/appearance). */
export function invalidateLoaderMusicCache() {
  cachedUrl = undefined;
  cachedPromise = null;
}

export function useLoaderMusic(enabled: boolean) {
  const urlRef = useRef<string | null>(null);
  // Resolve once on first mount (kept in module-level cache).
  useEffect(() => {
    let cancelled = false;
    resolveLoaderMusicUrl().then((u) => { if (!cancelled) urlRef.current = u; });
    return () => { cancelled = true; };
  }, []);

  // Setup the player with the URL when available. `useAudioPlayer` accepts
  // a stable ref-style argument; we re-evaluate cheaply on each render to
  // keep the hook order constant.
  const source = useMemo(() => {
    const u = urlRef.current;
    return u ? { uri: u } : null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlRef.current]);
  const player = useAudioPlayer(source);
  const status = useAudioPlayerStatus(player);

  // Loop on completion — Deep Import crawls can run 20–60s; the music must
  // outlast the loader.
  useEffect(() => {
    if (status?.didJustFinish && player) {
      try { player.seekTo(0); player.play(); } catch { /* noop */ }
    }
  }, [status?.didJustFinish, player]);

  // Respect prefers-reduced-motion on web — silent loader for users who
  // opted out of motion/audio fanfare.
  const reducedMotion =
    Platform.OS === 'web' &&
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Start/stop based on `enabled`. The user CLICK that opens Deep Import
  // satisfies the web autoplay policy — `.play()` therefore succeeds inside
  // this effect tick.
  useEffect(() => {
    if (!player) return;
    if (reducedMotion) return;
    let mounted = true;
    const run = async () => {
      try { await setAudioModeAsync({ playsInSilentMode: true }); } catch { /* noop */ }
      if (!mounted) return;
      if (enabled) {
        try { player.volume = 0.55; } catch { /* volume not supported on this platform */ }
        try { player.play(); } catch { /* autoplay blocked */ }
      } else {
        try { player.pause(); } catch { /* noop */ }
        try { player.seekTo(0); } catch { /* noop */ }
      }
    };
    void run();
    return () => { mounted = false; };
  }, [enabled, player, reducedMotion]);

  // On unmount: stop hard so we don't leave audio playing in the background
  // when the screen is torn down (modal close, route change).
  useEffect(() => {
    return () => {
      try { player?.pause(); } catch { /* noop */ }
    };
  }, [player]);

  return {
    available: !!urlRef.current,
    playing: !!status?.playing,
  };
}

export default useLoaderMusic;
