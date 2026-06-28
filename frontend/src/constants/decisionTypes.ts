/**
 * Canonical decision / life sub-types — ONE source of truth.
 * Order is user-mandated: Present Problem · Need · Future Risk · Aspiration.
 * Keys stay backward-compatible (`problem`,`need`,`aspiration`); `risk` is new.
 */
export type DecisionTypeKey = 'problem' | 'need' | 'risk' | 'aspiration';

export interface DecisionTypeCfg {
  key: DecisionTypeKey;
  label: string;       // singular display
  plural: string;      // plural display (counts/sections)
  short: string;       // 1-letter badge
  color: string;
  icon: string;        // Ionicons name
  desc: string;
}

export const DECISION_TYPES: DecisionTypeCfg[] = [
  { key: 'problem',    label: 'Present Problem', plural: 'Present Problems', short: 'P', color: '#EF4444', icon: 'alert-circle', desc: 'Solving a current challenge' },
  { key: 'need',       label: 'Need',            plural: 'Needs',            short: 'N', color: '#F59E0B', icon: 'bulb',         desc: 'Fulfilling a requirement' },
  { key: 'risk',       label: 'Future Risk',     plural: 'Future Risks',     short: 'R', color: '#F97316', icon: 'warning',      desc: 'Mitigating a future risk' },
  { key: 'aspiration', label: 'Aspiration',      plural: 'Aspirations',      short: 'A', color: '#10B981', icon: 'rocket',       desc: 'Pursuing a goal or ambition' },
];

export const DECISION_TYPE_KEYS: DecisionTypeKey[] = DECISION_TYPES.map(t => t.key);

export const DECISION_TYPE_CFG: Record<string, DecisionTypeCfg> =
  Object.fromEntries(DECISION_TYPES.map(t => [t.key, t]));

export const decisionTypeLabel = (key?: string | null): string =>
  (key && DECISION_TYPE_CFG[key]?.label) || '';
