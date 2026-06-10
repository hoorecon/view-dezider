import { useEffect, useState } from 'react';
import { Alert } from './crossAlert';
import api from './api';

export type Estimates = {
  tokens_per_credit: number;
  confirm_threshold_credits: number;
  features: Record<string, number>;
  default_estimate: number;
};

let _cache: Estimates | null = null;
let _inflight: Promise<Estimates | null> | null = null;

/** Fetch + cache the per-feature AI cost estimates (one network call, app-wide). */
export async function getEstimates(force = false): Promise<Estimates | null> {
  if (_cache && !force) return _cache;
  if (_inflight) return _inflight;
  _inflight = api.get('/ai-wallet/estimates')
    .then((r) => { _cache = r.data; _inflight = null; return _cache; })
    .catch(() => { _inflight = null; return null; });
  return _inflight;
}

/** Hook: returns the estimated credits for a feature (or null while loading). */
export function useAiEstimate(feature: string): number | null {
  const [credits, setCredits] = useState<number | null>(
    _cache ? (_cache.features[feature] ?? _cache.default_estimate) : null,
  );
  useEffect(() => {
    getEstimates().then((e) => {
      if (e) setCredits(e.features[feature] ?? e.default_estimate ?? null);
    });
  }, [feature]);
  return credits;
}

/**
 * Confirm before an AI spend estimated ABOVE the configured threshold
 * (default 15 credits). Resolves true to proceed, false to cancel. Below the
 * threshold (or if estimates can't be loaded) it proceeds without prompting.
 */
export async function confirmAiSpend(feature: string, label = 'This action'): Promise<boolean> {
  const est = await getEstimates();
  if (!est) return true;
  const credits = est.features[feature] ?? est.default_estimate;
  if (!credits || credits <= est.confirm_threshold_credits) return true;
  return new Promise<boolean>((resolve) => {
    Alert.alert(
      'Confirm AI usage',
      `${label} will use about ~${credits} AI credits. Continue?`,
      [
        { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
        { text: `Use ~${credits} cr`, onPress: () => resolve(true) },
      ],
      { cancelable: true, onDismiss: () => resolve(false) },
    );
  });
}
