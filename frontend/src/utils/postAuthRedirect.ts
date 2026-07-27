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
    // Guest quiz taken on quiz.jelcos.ai / /quiz — after sign-in we must
    // claim the token and reveal the result.
    const quizToken = await AsyncStorage.getItem('pending_quiz_token');
    if (quizToken) {
      await AsyncStorage.removeItem('pending_quiz_token');
      return `/quiz/result?token=${quizToken}`;
    }
    // A logged-out visitor tapped "Use this template" in The Decider Store.
    const clone = await AsyncStorage.getItem('pending_decider_clone');
    if (clone) {
      await AsyncStorage.removeItem('pending_decider_clone');
      const [tid, mode] = clone.split('::');
      if (tid) return `/decider-store/${tid}?use=${mode || 'full'}`;
    }
    const contribute = await AsyncStorage.getItem('pending_contribute_share');
    if (contribute) {
      await AsyncStorage.removeItem('pending_contribute_share');
      return `/contribute?share=${contribute}`;
    }
    const token = await AsyncStorage.getItem('pending_share_token');
    if (token) return `/shared/${token}`;
  } catch {
    /* ignore */
  }
  return '/(tabs)';
}
