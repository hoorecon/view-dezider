import { Alert } from 'react-native';
import api from './api';

/**
 * Centralised handler for metered-AI failures across the Emotional Gatekeeper
 * (and any other metered AI screen). Reads the structured backend error
 * `detail.code` and shows the right, actionable prompt:
 *
 *   - insufficient_credits → "Charge your AI Wallet"
 *   - ai_unavailable       → free quota exhausted → offer "Use OpenAI (shares
 *                            data)" consent OR top up
 *   - ai_error / other     → generic retry message
 *
 * @param error  the axios error
 * @param opts.router   expo-router router (for navigation to /ai-wallet)
 * @param opts.retry    optional callback to re-run the failed AI action
 */
export async function handleAiError(
  error: any,
  opts: { router: any; retry?: () => void },
): Promise<void> {
  const { router, retry } = opts;
  const detail = error?.response?.data?.detail;
  const code = detail && typeof detail === 'object' ? detail.code : undefined;
  const message = detail && typeof detail === 'object'
    ? detail.message
    : (typeof detail === 'string' ? detail : '');

  if (code === 'insufficient_credits') {
    Alert.alert(
      'Out of AI credits',
      message || "You're out of AI credits. Top up your AI Wallet to continue.",
      [
        { text: 'Not now', style: 'cancel' },
        { text: 'Charge Wallet', onPress: () => router.push('/ai-wallet') },
      ],
    );
    return;
  }

  if (code === 'ai_unavailable') {
    // Offer the free OpenAI route (shares data) only if it's configured and
    // the user hasn't already enabled it.
    let consent: any = { openai_available: false, allow_openai: false };
    try { consent = (await api.get('/ai-wallet/provider-consent')).data; } catch { /* ignore */ }

    if (consent.openai_available && !consent.allow_openai) {
      Alert.alert(
        'Free AI quota exhausted',
        (message || 'The free AI providers are momentarily exhausted.') +
        '\n\nYou can continue for free using OpenAI — note this shares your data with OpenAI. ' +
        'Or top up your AI Wallet to keep using the private providers.',
        [
          { text: 'Top up', onPress: () => router.push('/ai-wallet') },
          {
            text: 'Use OpenAI (share data)',
            onPress: async () => {
              try { await api.put('/ai-wallet/provider-consent', { allow_openai: true, mode: 'ask' }); } catch { /* ignore */ }
              retry?.();
            },
          },
        ],
      );
      return;
    }
    Alert.alert(
      'AI temporarily unavailable',
      message || 'Free quotas and your AI wallet may be exhausted. Top up, or enable OpenAI in AI Wallet settings.',
      [
        { text: 'OK', style: 'cancel' },
        { text: 'AI Wallet', onPress: () => router.push('/ai-wallet') },
      ],
    );
    return;
  }

  Alert.alert('AI error', message || 'Something went wrong with the AI. Please try again.');
}
