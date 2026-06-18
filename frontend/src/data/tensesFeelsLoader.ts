/**
 * Tenses & Feels content loader.
 *
 * Calls the new Content Library CMS API and falls back to the static
 * `tensesFeelsContent.ts` file when the network is unavailable or the
 * CMS has no blocks yet.
 *
 * Responsibilities:
 *   - Single source of truth for the 12 emotions + 3 healing feelings
 *   - Locale-aware (en default; future locales hi/ta/te/mr/kn auto fall
 *     back to en server-side via /content-library/render)
 *   - Module-level memoisation so repeated screen mounts reuse the same data
 *   - Idempotent — safe to call from useEffect on every mount
 */
import api from '../utils/api';
import {
  ALL_EMOTIONS,
  PAST_EMOTIONS, FUTURE_EMOTIONS,
  PRESENT_SELF_EMOTIONAL, PRESENT_SELF_MENTAL,
  PRESENT_OTHERS_YOURS, PRESENT_OTHERS_THEIRS,
  HEALING_FEELINGS, TENSES_FEELS_INTRO,
  EmotionDef, TenseCode, EmotionCategory,
} from './tensesFeelsContent';

export interface TensesFeelsBundle {
  all: EmotionDef[];
  past: EmotionDef[];
  future: EmotionDef[];
  present_self_emotional: EmotionDef[];
  present_self_mental: EmotionDef[];
  present_others_yours: EmotionDef[];
  present_others_theirs: EmotionDef[];
  healing: typeof HEALING_FEELINGS;
  intro: typeof TENSES_FEELS_INTRO;
  source: 'cms' | 'static';
  locale: string;
}

const STATIC_FALLBACK: TensesFeelsBundle = {
  all: ALL_EMOTIONS,
  past: PAST_EMOTIONS,
  future: FUTURE_EMOTIONS,
  present_self_emotional: PRESENT_SELF_EMOTIONAL,
  present_self_mental: PRESENT_SELF_MENTAL,
  present_others_yours: PRESENT_OTHERS_YOURS,
  present_others_theirs: PRESENT_OTHERS_THEIRS,
  healing: HEALING_FEELINGS,
  intro: TENSES_FEELS_INTRO,
  source: 'static',
  locale: 'en',
};

// Module-level cache keyed by locale. Cleared on hot reload.
const CACHE: Record<string, TensesFeelsBundle> = {};

function partition(emotions: EmotionDef[]): Omit<TensesFeelsBundle, 'all' | 'healing' | 'intro' | 'source' | 'locale'> {
  const past: EmotionDef[] = [];
  const future: EmotionDef[] = [];
  const pse: EmotionDef[] = [];
  const psm: EmotionDef[] = [];
  const poy: EmotionDef[] = [];
  const pot: EmotionDef[] = [];
  for (const e of emotions) {
    if (e.tense === 'past') past.push(e);
    else if (e.tense === 'future') future.push(e);
    else if (e.tense === 'present') {
      if (e.category === 'self_emotional') pse.push(e);
      else if (e.category === 'self_mental') psm.push(e);
      else if (e.category === 'others_yours') poy.push(e);
      else if (e.category === 'others_theirs') pot.push(e);
    }
  }
  return {
    past, future,
    present_self_emotional: pse,
    present_self_mental: psm,
    present_others_yours: poy,
    present_others_theirs: pot,
  };
}

function blockToEmotion(b: any): EmotionDef | null {
  const f = b?.fields || {};
  const code = b?.key;
  const label = b?.title || f.title;
  if (!code || !label) return null;
  return {
    code,
    label,
    short: b?.short || f.short || '',
    tense: (f.tense || 'present') as TenseCode,
    polarity: (f.polarity || 'negative') as 'negative' | 'positive',
    category: (f.category || 'none') as EmotionCategory,
    color: f.color || '#5B7CFA',
    narrative_paraphrase: f.narrative_paraphrase || '',
    power_statement: f.power_statement || '',
    instruction_for_user: f.instruction_for_user || '',
    resolution_quote: f.resolution_quote || '',
    healing_feeling: (f.healing_feeling || 'gratefulness') as EmotionDef['healing_feeling'],
    verbatim_script: f.verbatim_script || undefined,
  };
}

/**
 * Load Tenses & Feels content with CMS-first / static-fallback strategy.
 *
 * @param locale  ISO 639-1 code (en/hi/ta/te/mr/kn). Backend falls back to en.
 * @param forceRefresh  bypass cache.
 */
export async function loadTensesFeels(
  locale: string = 'en',
  forceRefresh: boolean = false,
): Promise<TensesFeelsBundle> {
  const key = locale.toLowerCase();
  if (!forceRefresh && CACHE[key]) return CACHE[key];

  try {
    const { data } = await api.get(`/content-library/render/tenses_feels?locale=${key}`, {
      // Avoid blocking the UI for too long — fall back if slow
      timeout: 5000,
    } as any);
    const blocks = Array.isArray(data?.blocks) ? data.blocks : [];
    if (blocks.length === 0) {
      // CMS not yet seeded — return static and DO NOT cache so a later seed
      // call from admin becomes visible on next mount.
      return { ...STATIC_FALLBACK, locale: key };
    }
    const emotions = blocks
      .map(blockToEmotion)
      .filter((x): x is EmotionDef => !!x)
      .sort((a: any, b: any) => (a.order ?? 999) - (b.order ?? 999));
    const part = partition(emotions);
    const bundle: TensesFeelsBundle = {
      all: emotions,
      ...part,
      healing: HEALING_FEELINGS,           // healing list is static (3 fixed)
      intro: TENSES_FEELS_INTRO,           // intro copy is static
      source: 'cms',
      locale: key,
    };
    CACHE[key] = bundle;
    return bundle;
  } catch {
    // Network/CMS down — fall back to bundled static content
    return { ...STATIC_FALLBACK, locale: key };
  }
}

/** Clear the cache (e.g. when admin edits content live). */
export function invalidateTensesFeelsCache() {
  for (const k of Object.keys(CACHE)) delete CACHE[k];
}
