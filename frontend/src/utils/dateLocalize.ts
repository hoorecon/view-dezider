/**
 * dateLocalize — format an ISO date per user country / preference.
 *
 * Default per country:
 *   IN, AU, NZ, GB, IE     → DD-MMM-YYYY  (e.g., 15-Aug-2026)
 *   US                      → MMM DD, YYYY (e.g., Aug 15, 2026)
 *   DE, FR, ES, IT, NL      → DD.MM.YYYY
 *   JP, CN, KR              → YYYY-MM-DD
 *   else                    → DD-MMM-YYYY  (Indian default)
 *
 * User can override via profile.date_format_preference if/when added.
 */

export type DateFormat = 'DD-MMM-YYYY' | 'MMM DD, YYYY' | 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'DD.MM.YYYY' | 'YYYY-MM-DD';

const COUNTRY_FORMAT_MAP: Record<string, DateFormat> = {
  IN: 'DD-MMM-YYYY',
  AU: 'DD-MMM-YYYY',
  NZ: 'DD-MMM-YYYY',
  GB: 'DD-MMM-YYYY',
  IE: 'DD-MMM-YYYY',
  US: 'MMM DD, YYYY',
  CA: 'MMM DD, YYYY',
  DE: 'DD.MM.YYYY',
  FR: 'DD/MM/YYYY',
  ES: 'DD/MM/YYYY',
  IT: 'DD/MM/YYYY',
  NL: 'DD-MM-YYYY' as DateFormat,
  JP: 'YYYY-MM-DD',
  CN: 'YYYY-MM-DD',
  KR: 'YYYY-MM-DD',
};

const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export function getDefaultDateFormat(user?: { country_code?: string; date_format_preference?: DateFormat | string | null }): DateFormat {
  if (user?.date_format_preference) return user.date_format_preference as DateFormat;
  const cc = (user?.country_code || 'IN').toUpperCase();
  return COUNTRY_FORMAT_MAP[cc] || 'DD-MMM-YYYY';
}

export function formatLocalized(iso?: string | null, fmt: DateFormat = 'DD-MMM-YYYY'): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  const mmm = MONTHS_SHORT[d.getMonth()];
  switch (fmt) {
    case 'MMM DD, YYYY': return `${mmm} ${dd}, ${yyyy}`;
    case 'DD/MM/YYYY':   return `${dd}/${mm}/${yyyy}`;
    case 'MM/DD/YYYY':   return `${mm}/${dd}/${yyyy}`;
    case 'DD.MM.YYYY':   return `${dd}.${mm}.${yyyy}`;
    case 'YYYY-MM-DD':   return `${yyyy}-${mm}-${dd}`;
    case 'DD-MMM-YYYY':
    default:             return `${dd}-${mmm}-${yyyy}`;
  }
}

export function addDaysISO(days: number, from: Date = new Date()): string {
  const d = new Date(from);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Returns 'in 5 days', 'in 2 weeks', 'overdue 3 days', etc. */
export function deadlineCountdown(iso?: string | null): { text: string; severity: 'ok' | 'warn' | 'danger' | 'overdue' } | null {
  if (!iso) return null;
  const target = new Date(iso);
  if (isNaN(target.getTime())) return null;
  const now = new Date(); now.setHours(0,0,0,0);
  const targetDay = new Date(target); targetDay.setHours(0,0,0,0);
  const diffDays = Math.round((targetDay.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays < 0)  return { text: `overdue ${Math.abs(diffDays)}d`,  severity: 'overdue' };
  if (diffDays === 0) return { text: 'due today',                       severity: 'danger' };
  if (diffDays <= 3)  return { text: `in ${diffDays}d`,                  severity: 'danger' };
  if (diffDays <= 14) return { text: `in ${diffDays}d`,                  severity: 'warn' };
  if (diffDays <= 60) return { text: `in ${Math.round(diffDays/7)}w`,    severity: 'ok' };
  if (diffDays <= 730) return { text: `in ${Math.round(diffDays/30)}mo`, severity: 'ok' };
  return { text: `in ${Math.round(diffDays/365)}y`, severity: 'ok' };
}

export function formatHorizon(value?: number | null, unit?: string | null): string {
  if (!value) return '';
  const u = (unit || 'days').toLowerCase();
  const singular: Record<string, string> = { day: 'day', week: 'week', month: 'month', year: 'year' };
  const plural: Record<string, string>   = { day: 'days', week: 'weeks', month: 'months', year: 'years' };
  const base = u.replace(/s$/, '');
  return value === 1 ? `${value} ${singular[base] || base}` : `${value} ${plural[base] || u}`;
}
