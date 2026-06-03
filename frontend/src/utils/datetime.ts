/**
 * Date / timestamp helpers used across all list cards so users can
 * disambiguate similarly-titled items by recency.
 */

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function _parse(input: any): Date | null {
  if (!input) return null;
  if (input instanceof Date) return isNaN(input.getTime()) ? null : input;
  // Accept ISO, MongoDB-style "2026-05-30T18:51:00.123Z", or epoch (s/ms)
  if (typeof input === 'number') {
    const d = new Date(input < 1e12 ? input * 1000 : input);
    return isNaN(d.getTime()) ? null : d;
  }
  if (typeof input === 'string') {
    // Date-only string ⇒ keep as local midnight
    const s = input.length === 10 ? `${input}T00:00:00` : input;
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }
  return null;
}

/** "Jun 5, 06:51 PM" (current year) · "5 Jun 2025, 06:51 PM" (older) */
export function formatAbsolute(input: any): string {
  const d = _parse(input);
  if (!d) return '';
  const now = new Date();
  const sameYear = d.getFullYear() === now.getFullYear();
  const dd = d.getDate();
  const mo = MONTHS[d.getMonth()];
  const yr = d.getFullYear();
  let h = d.getHours();
  const m = d.getMinutes().toString().padStart(2, '0');
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  return sameYear
    ? `${dd} ${mo}, ${h}:${m} ${ampm}`
    : `${dd} ${mo} ${yr}, ${h}:${m} ${ampm}`;
}

/** "DD-MM-YYYY" — for date-only fields (action deadlines, review dates). */
export function formatDMY(input: any): string {
  const d = _parse(input);
  if (!d) return '';
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${dd}-${mm}-${d.getFullYear()}`;
}

/** "just now" · "5m ago" · "2h ago" · "yesterday" · "3d ago" · "Jun 5" */
export function formatRelative(input: any): string {
  const d = _parse(input);
  if (!d) return '';
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 30) return 'just now';
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  if (diff < 172800) return 'yesterday';
  if (diff < 604800) return `${Math.floor(diff/86400)}d ago`;
  if (diff < 2629800) return `${Math.floor(diff/604800)}w ago`;
  return formatAbsolute(d);
}

/**
 * Best-effort timestamp picker — accepts an object and returns the most
 * relevant timestamp. Prefers updated_at when meaningfully newer than
 * created_at; falls back to created_at; finally to any date-ish field.
 */
export function bestTimestamp(obj: any): { ts: any; label: 'updated' | 'created' | null } {
  if (!obj) return { ts: null, label: null };
  const c = obj.created_at || obj.createdAt;
  const u = obj.updated_at || obj.updatedAt;
  const cd = _parse(c);
  const ud = _parse(u);
  if (ud && cd && Math.abs(ud.getTime() - cd.getTime()) > 60 * 1000) {
    return { ts: u, label: 'updated' };
  }
  if (cd) return { ts: c, label: 'created' };
  if (ud) return { ts: u, label: 'updated' };
  return { ts: null, label: null };
}
