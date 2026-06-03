import { Redirect } from 'expo-router';

/**
 * Legacy route — the "Shared with me" experience now lives as a primary tab
 * (next to Solution Box). Keep this path alive for old deep-links/bookmarks
 * by redirecting into the tab.
 */
export default function SharedWithMeLegacyRedirect() {
  return <Redirect href="/(tabs)/shared" />;
}
