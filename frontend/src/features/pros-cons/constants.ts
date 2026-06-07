/* Pros & Cons wizard — static constants (extracted). */
import { LIFE_AREAS as LIFE_AREAS_CANONICAL } from '../../constants/lifeAreas';

export const STEPS = [
  { n: 1, label: 'Factors' },
  { n: 2, label: 'Options' },
  { n: 3, label: 'Promote' },
  { n: 4, label: 'Group' },
  { n: 5, label: 'Review' },
  { n: 6, label: 'Mandatory' },
  { n: 7, label: 'Prioritize & Assess' },
  { n: 8, label: 'Assess' },
];

export const LIFE_AREAS = LIFE_AREAS_CANONICAL.map(a => ({ key: a.id, label: a.short, icon: a.icon }));

export const COLORS = {
  primary: '#6366F1', primaryDark: '#4F46E5',
  pro: '#059669', con: '#DC2626', direct: '#0369A1',
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0',
  text: '#0F172A', textDim: '#64748B', warn: '#EA580C', ok: '#16A34A',
  mandatory: '#EA580C',  // orange — Step 6 "A" / Step 7 top section
  optional: '#0F172A',   // dark slate — Step 6 "B" / Step 7 bottom section
};
