// PostHog product analytics (EU cloud) for the Expo web app.
//
// Privacy: users are identified by their non-PII `user_id` ONLY — never
// email/name/phone. No-op when EXPO_PUBLIC_POSTHOG_KEY is absent (dev),
// so the app never breaks without analytics configured.
import PostHog from 'posthog-react-native';

const KEY = process.env.EXPO_PUBLIC_POSTHOG_KEY;
const HOST = process.env.EXPO_PUBLIC_POSTHOG_HOST || 'https://eu.i.posthog.com';

let client: PostHog | null = null;
if (KEY) {
  try {
    client = new PostHog(KEY, {
      host: HOST,
      // Web build: SDK auto-detects @react-native-async-storage for persistence.
      captureAppLifecycleEvents: false,
    });
  } catch {
    client = null;
  }
}

/** Pageview on every route change; also derives tool_opened for /tools/*. */
export const trackScreen = (pathname: string, params?: Record<string, any>) => {
  if (!client) return;
  try {
    client.screen(pathname || '/', params);
    if (pathname?.startsWith('/tools/')) {
      client.capture('tool_opened', { tool: pathname.replace('/tools/', '') });
    }
  } catch { /* analytics must never break the app */ }
};

export const trackEvent = (name: string, props?: Record<string, any>) => {
  if (!client) return;
  try { client.capture(name, props); } catch { /* no-op */ }
};

let identified = false;

/** Identify by non-PII user_id only. Safe to call repeatedly. */
export const identifyUser = (userId: string) => {
  if (!client || !userId) return;
  try { client.identify(userId); identified = true; } catch { /* no-op */ }
};

/** Unlink the device from the previous user (call on logout). */
export const resetAnalytics = () => {
  if (!client || !identified) return;
  try { client.reset(); identified = false; } catch { /* no-op */ }
};
