import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * Decide where to send a user immediately after a successful login.
 *
 * If they arrived via a shared-report deep link (we stashed
 * `pending_share_token` before bouncing them to login), route them straight
 * to the deep-link target which accepts the share and opens "Shared with me".
 * Otherwise fall back to the app dashboard.
 *
 * Centralising this avoids the previous bug where each auth-completion point
 * hardcoded `/(tabs)` and relied on a racy dashboard-mount effect to redirect.
 */
export async function getPostAuthRoute(): Promise<string> {
  try {
    const token = await AsyncStorage.getItem('pending_share_token');
    if (token) return `/shared/${token}`;
  } catch {
    /* ignore */
  }
  return '/(tabs)';
}
