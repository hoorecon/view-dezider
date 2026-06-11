// PostHog product analytics (EU cloud) for the Expo app.
//
// Privacy: users are identified by their non-PII `user_id` ONLY — never
// email/name/phone. No-op when EXPO_PUBLIC_POSTHOG_KEY is absent (dev),
// so the app never breaks without analytics configured.
//
// Platform split:
//   • Web   → posthog-js (supports SESSION REPLAY; the RN SDK does not on web).
//             Replay is privacy-hardened: all inputs masked, no network
//             request/response bodies captured (tokens/PII never recorded).
//   • Native→ posthog-react-native (events only).
import { Platform } from 'react-native';

const KEY = process.env.EXPO_PUBLIC_POSTHOG_KEY;
const HOST = process.env.EXPO_PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com';

// Unified minimal client interface used by the helpers below.
let webClient: any = null;  // posthog-js singleton (web only)
let rnClient: any = null;   // posthog-react-native instance (native only)

if (KEY) {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const posthog = require('posthog-js').default;
      posthog.init(KEY, {
        api_host: HOST,
        // SPA: pageviews are captured manually on every expo-router change
        // (see trackScreen), so disable the automatic one to avoid duplicates.
        capture_pageview: false,
        capture_pageleave: true,
        persistence: 'localStorage+cookie',
        person_profiles: 'identified_only',
        autocapture: true,
        // ------------------ SESSION REPLAY (privacy-first) ------------------
        disable_session_recording: false,
        session_recording: {
          maskAllInputs: true,                 // never record typed input values
          maskInputOptions: { password: true } as any,
          recordCrossOriginIframes: false,
        },
        // Never capture network request/response bodies (would leak JWTs/PII).
        capture_performance: false,
      });
      // Expose for runtime verification (e.g. posthog.sessionRecordingStarted()
      // in DevTools). Standard practice; the API key is public by design.
      (window as any).posthog = posthog;
      webClient = posthog;
    } catch {
      webClient = null;
    }
  } else {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const PostHog = require('posthog-react-native').default;
      rnClient = new PostHog(KEY, {
        host: HOST,
        captureAppLifecycleEvents: false,
      });
    } catch {
      rnClient = null;
    }
  }
}

/** Pageview on every route change; also derives tool_opened for /tools/*. */
export const trackScreen = (pathname: string, params?: Record<string, any>) => {
  try {
    if (webClient) {
      webClient.capture('$pageview', {
        $current_url: typeof window !== 'undefined' ? window.location.href : pathname,
        screen: pathname || '/',
        ...params,
      });
    } else if (rnClient) {
      rnClient.screen(pathname || '/', params);
    } else {
      return;
    }
    if (pathname?.startsWith('/tools/')) {
      const props = { tool: pathname.replace('/tools/', '') };
      if (webClient) webClient.capture('tool_opened', props);
      else rnClient?.capture('tool_opened', props);
    }
  } catch { /* analytics must never break the app */ }
};

export const trackEvent = (name: string, props?: Record<string, any>) => {
  try {
    if (webClient) webClient.capture(name, props);
    else if (rnClient) rnClient.capture(name, props);
  } catch { /* no-op */ }
};

let identified = false;

/** Identify by non-PII user_id only. Safe to call repeatedly. */
export const identifyUser = (userId: string) => {
  if (!userId) return;
  try {
    if (webClient) { webClient.identify(userId); identified = true; }
    else if (rnClient) { rnClient.identify(userId); identified = true; }
  } catch { /* no-op */ }
};

/** Unlink the device from the previous user (call on logout). */
export const resetAnalytics = () => {
  if (!identified) return;
  try {
    if (webClient) { webClient.reset(); identified = false; }
    else if (rnClient) { rnClient.reset(); identified = false; }
  } catch { /* no-op */ }
};
