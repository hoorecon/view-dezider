/**
 * Canonical Action-Item status vocabulary — one source of truth shared by
 * Action Center, CTT, Lifestyle and the Action-Plan steps of Pros & Cons /
 * My Dezider / Solution Finder. Legacy values are aliased so old data renders.
 */

export type ActionStatus =
  | 'pending' | 'wip_25' | 'wip_50' | 'wip_75'
  | 'done' | 'deferred' | 'blocked' | 'cancelled';

export type StatusOpt = { id: ActionStatus; label: string; color: string; progress?: number };

export const ACTION_STATUS_OPTS: StatusOpt[] = [
  { id: 'pending',   label: 'Pending',   color: '#94A3B8', progress: 0 },
  { id: 'wip_25',    label: 'WIP 25%',   color: '#60A5FA', progress: 25 },
  { id: 'wip_50',    label: 'WIP 50%',   color: '#3B82F6', progress: 50 },
  { id: 'wip_75',    label: 'WIP 75%',   color: '#6366F1', progress: 75 },
  { id: 'done',      label: 'Done',      color: '#10B981', progress: 100 },
  { id: 'deferred',  label: 'Deferred',  color: '#A855F7' },
  { id: 'blocked',   label: 'Blocked',   color: '#EF4444' },
  { id: 'cancelled', label: 'Cancelled', color: '#A1A1AA' },
];

const BY_ID: Record<string, StatusOpt> = ACTION_STATUS_OPTS.reduce(
  (m, o) => { m[o.id] = o; return m; }, {} as Record<string, StatusOpt>);

const ALIAS: Record<string, ActionStatus> = {
  open: 'pending',
  in_progress: 'wip_50',
  'in progress': 'wip_50',
  completed: 'done',
  complete: 'done',
  '': 'pending',
};

export function normStatus(s?: string | null): ActionStatus {
  if (!s) return 'pending';
  const v = String(s).trim().toLowerCase();
  if (BY_ID[v]) return v as ActionStatus;
  return ALIAS[v] || 'pending';
}

export function statusLabel(s?: string | null): string {
  return BY_ID[normStatus(s)].label;
}

export function statusColor(s?: string | null): string {
  return BY_ID[normStatus(s)].color;
}

export function statusProgress(s?: string | null): number {
  return BY_ID[normStatus(s)].progress ?? 0;
}
