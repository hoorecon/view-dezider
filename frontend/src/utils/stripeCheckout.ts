import { Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import api from './api';

export type StripeKind = 'ai_wallet' | 'subscription';
export type StripeCurrency = 'usd' | 'inr';

export interface StartStripeArgs {
  kind: StripeKind;
  currency: StripeCurrency;
  pack_id?: string;
  credits?: number;
  plan_id?: string;
}

/**
 * Kick off a Stripe Checkout session and route the user to Stripe's hosted page.
 *
 * Web  → full-page redirect to Stripe; on return, `app/checkout-result.tsx`
 *        reads `?stripe_session=…` and polls for fulfillment.
 * Native → opens Stripe in an auth session and polls status on return.
 *
 * Returns { status } on native ('completed' | 'pending' | 'cancelled'); on web
 * it never resolves (the page navigates away).
 */
export async function startStripeCheckout(
  args: StartStripeArgs,
): Promise<{ status: string; session_id?: string }> {
  const isWeb = Platform.OS === 'web';

  // Where Stripe should send the user back to.
  const successUrl = isWeb
    ? `${window.location.origin}/checkout-result`
    : Linking.createURL('/checkout-result');
  const cancelUrl = isWeb
    ? `${window.location.origin}/checkout-result?stripe_cancelled=1`
    : Linking.createURL('/checkout-result', { queryParams: { stripe_cancelled: '1' } });

  const res = await api.post('/stripe/checkout', {
    kind: args.kind,
    currency: args.currency,
    pack_id: args.pack_id,
    credits: args.credits,
    plan_id: args.plan_id,
    success_url: successUrl,
    cancel_url: cancelUrl,
  });
  const { checkout_url, session_id } = res.data as { checkout_url: string; session_id: string };

  if (isWeb) {
    window.location.href = checkout_url;
    return { status: 'pending', session_id };
  }

  const result = await WebBrowser.openAuthSessionAsync(checkout_url, successUrl);
  if (result.type !== 'success') {
    return { status: 'cancelled', session_id };
  }
  const status = await pollStripeStatus(session_id);
  return { status, session_id };
}

/** Poll `/stripe/status/{id}` until completed/failed or timeout (~40s). */
export async function pollStripeStatus(sessionId: string, tries = 20): Promise<string> {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await api.get(`/stripe/status/${sessionId}`);
      const s = r.data?.status;
      if (s === 'completed' || s === 'failed') return s;
    } catch {
      // transient — keep polling
    }
    await new Promise((res) => setTimeout(res, 2000));
  }
  return 'pending';
}
