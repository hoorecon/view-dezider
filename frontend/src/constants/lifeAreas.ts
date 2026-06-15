/**
 * Canonical Life Areas — Single Source of Truth
 *
 * IMPORTANT: All flows (Decider / Pros & Cons / Pros & Cons 8-Step / SWOT /
 * GEM / Lifestyle / Solution Matrix / Solution Finder) MUST import from this
 * file. Do NOT define local copies — they drift apart and cause UX bugs like
 * collapsing "Social Image" and "Social Contributions" into a single "Social".
 *
 * Canonical mapping mirrors the backend in /app/backend/models/decisions_models.py
 */

export type LifeAreaId =
  | 'holistic_health'
  | 'knowledge_skills'
  | 'relationships'
  | 'finance'
  | 'assets'
  | 'career'
  | 'hobbies_entertainment'
  | 'social_image'
  | 'social_contributions'
  | 'spirituality_religion';

export interface LifeArea {
  id: LifeAreaId;
  /** Full canonical name (use in detail pages / lists) */
  name: string;
  /** Short label (≤ 12 chars, use in compact chips / filter bars) */
  short: string;
  /** Ionicons name */
  icon: string;
  /** Brand color (used for badge/border/background tint) */
  color: string;
}

export const LIFE_AREAS: LifeArea[] = [
  { id: 'holistic_health',       name: 'Holistic Health',          short: 'Health',         icon: 'fitness',         color: '#10B981' },
  { id: 'knowledge_skills',      name: 'Knowledge & Skills',       short: 'Knowledge',      icon: 'school',          color: '#3B82F6' },
  { id: 'relationships',         name: 'Relationships',            short: 'Relationships',  icon: 'heart',           color: '#EC4899' },
  { id: 'finance',               name: 'Finance',                  short: 'Finance',        icon: 'cash',            color: '#F59E0B' },
  { id: 'assets',                name: 'Assets',                   short: 'Assets',         icon: 'home',            color: '#8B5CF6' },
  { id: 'career',                name: 'Career',                   short: 'Career',         icon: 'briefcase',       color: '#6366F1' },
  { id: 'hobbies_entertainment', name: 'Hobbies & Entertainment',  short: 'Hobbies',        icon: 'game-controller', color: '#14B8A6' },
  { id: 'social_image',          name: 'Social Image & Influence', short: 'Social Image',   icon: 'star',            color: '#F97316' },
  { id: 'social_contributions',  name: 'Social Contributions',     short: 'Contributions',  icon: 'people',          color: '#06B6D4' },
  { id: 'spirituality_religion', name: 'Spirituality & Religion',  short: 'Spirituality',   icon: 'leaf',            color: '#A855F7' },
];

export const LIFE_AREA_BY_ID: Record<string, LifeArea> = LIFE_AREAS.reduce(
  (acc, a) => { acc[a.id] = a; return acc; },
  {} as Record<string, LifeArea>,
);

// Canonical → legacy slug map. Lets callers pass EITHER form to the helpers
// below. Backend rows that have been migrated to canonical IDs (la_career,
// la_finance, …) still resolve to the same display label/icon/color.
const CANONICAL_TO_LEGACY: Record<string, string> = {
  la_career:        'career',
  la_finance:       'finance',
  la_relationships: 'relationships',
  la_health:        'holistic_health',
  la_assets:        'assets',
  la_knowledge:     'knowledge_skills',
  la_social_image:  'social_image',
  la_contribution:  'social_contributions',
  la_hobbies:       'hobbies_entertainment',
  la_spirituality:  'spirituality_religion',
};

/** Safe lookup — accepts both legacy slug (`career`) and canonical id
 *  (`la_career`). Returns undefined if id is missing/unknown. */
export function getLifeArea(id?: string | null): LifeArea | undefined {
  if (!id) return undefined;
  if (LIFE_AREA_BY_ID[id]) return LIFE_AREA_BY_ID[id];
  const legacy = CANONICAL_TO_LEGACY[id];
  return legacy ? LIFE_AREA_BY_ID[legacy] : undefined;
}

/** Safe display name — falls back to id-as-string or empty */
export function getLifeAreaName(id?: string | null, fallback: string = ''): string {
  return getLifeArea(id)?.name ?? fallback;
}

/** Safe short label — for compact UIs */
export function getLifeAreaShort(id?: string | null, fallback: string = ''): string {
  return getLifeArea(id)?.short ?? fallback;
}

/** Safe icon name — falls back to a generic glyph */
export function getLifeAreaIcon(id?: string | null, fallback: string = 'ellipse'): string {
  return getLifeArea(id)?.icon ?? fallback;
}

/** Safe color hex — falls back to neutral grey */
export function getLifeAreaColor(id?: string | null, fallback: string = '#8B5CF6'): string {
  return getLifeArea(id)?.color ?? fallback;
}
