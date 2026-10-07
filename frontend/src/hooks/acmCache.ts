/**
 * Shared in-memory cache for /api/acm/my-access.
 *
 * Kept separate from useACM so authStore can reset it on login/logout
 * without importing useACM (which itself imports authStore).
 */
export const acmCache: {
  data: any | null;
  inflight: Promise<any | null> | null;
  token: string | null | undefined;
} = {
  data: null,
  inflight: null,
  token: undefined,
};

export function clearAcmCache() {
  acmCache.data = null;
  acmCache.inflight = null;
}
