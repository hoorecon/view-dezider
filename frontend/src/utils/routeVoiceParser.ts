/**
 * routeVoiceParser.ts
 *
 * Multilingual voice-command parser for app-wide navigation to tools/modules.
 * Scope is intentionally limited to MODULE / SUB-TOOL SELECTION
 * (not for step-level data entry — that's handled by separate parsers
 * like `stepVoiceParser.ts`).
 *
 * Supported languages: English (en), Hindi (hi), Tamil (ta), Telugu (te),
 * Kannada (kn), Malayalam (ml).
 *
 * Matching is phrase-based (case-insensitive, accent-insensitive).
 *
 * Returns a `RouteIntent` the caller can push into expo-router, or `null`
 * when no recognised intent is found.
 */

export type SupportedLanguage = 'en' | 'hi' | 'ta' | 'te' | 'kn' | 'ml';

export interface SupportedLanguageMeta {
  code: SupportedLanguage;
  label: string;
  bcp47: string; // full locale for ExpoSpeechRecognition
  nativeLabel: string;
}

export const VOICE_NAV_LANGUAGES: SupportedLanguageMeta[] = [
  { code: 'en', label: 'English', bcp47: 'en-IN', nativeLabel: 'English' },
  { code: 'hi', label: 'Hindi', bcp47: 'hi-IN', nativeLabel: 'हिन्दी' },
  { code: 'ta', label: 'Tamil', bcp47: 'ta-IN', nativeLabel: 'தமிழ்' },
  { code: 'te', label: 'Telugu', bcp47: 'te-IN', nativeLabel: 'తెలుగు' },
  { code: 'kn', label: 'Kannada', bcp47: 'kn-IN', nativeLabel: 'ಕನ್ನಡ' },
  { code: 'ml', label: 'Malayalam', bcp47: 'ml-IN', nativeLabel: 'മലയാളം' },
];

export interface RouteDefinition {
  id: string;
  path: string;         // expo-router path
  label: string;        // English label, for UI and history
  icon: string;         // Ionicons name (for hint chip)
  /**
   * Keywords per language. Only *distinctive* keywords for the destination.
   * The parser uses substring match (after accent-fold + lowercase), so
   * keep them short and unambiguous.
   */
  keywords: Record<SupportedLanguage, string[]>;
}

export interface RouteIntent {
  route: RouteDefinition;
  language: SupportedLanguage;
  matchedPhrase: string;
}

// -----------------------------------------------------------------------
// Route dictionary — primary tools / hubs the user would reach by voice.
// Add more entries as the app grows. Duplicated native keywords are OK
// (parser always prefers the longer match).
// -----------------------------------------------------------------------
export const ROUTE_DICTIONARY: RouteDefinition[] = [
  {
    id: 'home',
    path: '/(tabs)',
    label: 'Home',
    icon: 'home',
    keywords: {
      en: ['home', 'main screen', 'dashboard'],
      hi: ['घर', 'होम', 'मुख्य'],
      ta: ['வீடு', 'முகப்பு'],
      te: ['ఇల்லு', 'ఇల்லు', 'ముఖ೗ళం'],
      kn: ['ಮನೆ', 'ಮುಖಪುಟ'],
      ml: ['വീട്', 'ഹોം'],
    },
  },
  {
    id: 'journal',
    path: '/(tabs)/journal',
    label: 'Journal',
    icon: 'book',
    keywords: {
      en: ['journal', 'my journal', 'diary'],
      hi: ['डायरी', 'जर्नल'],
      ta: ['சேமிப்பு', 'நாட்குறிப்பேடு'],
      te: ['డైరೀ', 'జರ್ನಲ್'],
      kn: ['ಡೈರಿ', 'ಜರ್ನಲ್'],
      ml: ['ഡെയറി', 'ജേണല്'],
    },
  },
  {
    id: 'decisions',
    path: '/(tabs)/prr',
    label: 'My Decisions',
    icon: 'document-text',
    keywords: {
      en: ['my decisions', 'decisions', 'prr', 'my dezider'],
      hi: ['मेरे फैसले', 'फैसले', 'निर्णय'],
      ta: ['என્தீர்माனங்கள்', 'தீர்மाனம்'],
      te: ['నா నிರ்ಣ೑యாலು', 'నிರ்ಣ೑యாலು'],
      kn: ['ನிರ்ಧாರಗಳು', 'ನிರ்ಧாರ'],
      ml: ['തീരുമാനങ്ങൾ', 'തീരുമാനം'],
    },
  },
  {
    id: 'test123',
    path: '/(tabs)/test123',
    label: 'Instant Dezider',
    icon: 'flash',
    keywords: {
      en: ['instant dezider', 'instant decider', 'test123', 'test 123', 'quick decision', 'test one two three'],
      hi: ['टेस्ट टाइडेड टरी'],
      ta: ['டெஸ்ட் ஒன்று இரண்டு மூன்று'],
      te: ['టெச்ட் ஒன்று ತூன்று மூன்று'],
      kn: ['ಥெச்ட் ஒன்று ತூன்று மூன்று'],
      ml: ['ടെസ്റ് ඒன்று ತூன்று மூன்று'],
    },
  },
  // -------- tool list/hub pages --------
  {
    id: 'solution_matrix_list',
    path: '/tools/solution-matrix-list',
    label: 'Solution Matrix',
    icon: 'grid',
    keywords: {
      en: ['solution matrix', 'matrix', 'matrices', 'my matrices'],
      hi: ['सोल्यूशन मैट्रिक्स', 'निवारण मैट्रिक्स', 'मैट्रिक्स'],
      ta: ['தீர்வு மாட்ரிக்ஸ்', 'மாட்ரிக்ஸ்'],
      te: ['సలುషುన್ மாட்ரிக்ஸ்', 'மாட்ரிக்ஸ்'],
      kn: ['ಪರಿಹಾರ ಮ್ಯாட்ரிக்ஸ்', 'மாட்ரிக்ஸ்'],
      ml: ['പരിഹാര മാട്രിക്സ்', 'മാട്രിക്സ்'],
    },
  },
  {
    id: 'solution_finder',
    path: '/tools/solution-finder-list',
    label: 'Solution Finder',
    icon: 'search',
    keywords: {
      en: ['solution finder', 'simple solution', 'find solution'],
      hi: ['सोल्यूशन फाइंडर', 'समाधान खोज'],
      ta: ['தீர்வு கண்டுபிடி'],
      te: ['సలುషುన್ பாக்கீர்வு'],
      kn: ['ಪರಿಹಾರ கண்டுபிடி'],
      ml: ['പരിഹാരം കണ்டுபிடி'],
    },
  },
  {
    id: 'goal_setter',
    path: '/tools/goal-setter',
    label: 'Goal Setter',
    icon: 'flag',
    keywords: {
      en: ['goal setter', 'set goal', 'goals', 'goal setting'],
      hi: ['लक्ष्य निर्धारण', 'लक्ष्य'],
      ta: ['இலக்கு அமைப்பான்', 'இலக்கு'],
      te: ['ଲக்ஷ்ய நிர்ணாரண', 'ଲக்ஷ்ய'],
      kn: ['ಮಾರ೒ಲು', '஗ರಿ ಸಿಹர்'],
      ml: ['ലക്ഷ്യം', 'മാര്ഗா'],
    },
  },
  {
    id: 'conflict_breaker',
    path: '/tools/conflict-breaker',
    label: 'Conflict Breaker',
    icon: 'flash-off',
    keywords: {
      en: ['conflict breaker', 'conflict', 'conflicts'],
      hi: ['संघर्ष हल'],
      ta: ['म।லு भंजन'],
      te: ['கலப்बम्'],
      kn: ['஘ರிக್ಷ உರோಧ'],
      ml: ['തര்கவाி'],
    },
  },
  {
    id: 'cld_engine',
    path: '/tools/cld-engine',
    label: 'CLD Engine',
    icon: 'git-branch',
    keywords: {
      en: ['cld', 'cld engine', 'causal loop'],
      hi: ['सीएलडी इंजन', 'सीएलडी'],
      ta: ['சிஎல்டி यंजना'],
      te: ['సிஎல்டி'],
      kn: ['ಸிஎல்டி'],
      ml: ['സிஎல்டி'],
    },
  },
  {
    id: 'tepfi',
    path: '/tools/tepfi',
    label: 'TEPFI',
    icon: 'apps',
    keywords: {
      en: ['tepfi', 'tepfi matrix'],
      hi: ['टेप्फी'],
      ta: ['டெப்फी'],
      te: ['టெப்फी'],
      kn: ['ಡெப்फी'],
      ml: ['ടெப்फी'],
    },
  },
  {
    id: 'swot',
    path: '/tools/swot',
    label: 'SWOT Analysis',
    icon: 'analytics',
    keywords: {
      en: ['swot', 'swot analysis'],
      hi: ['एसडब्ल्यूओटी', 'सवॉट'],
      ta: ['ஸ्வாट्'],
      te: ['స்வாट्'],
      kn: ['ಸ்வாट्'],
      ml: ['സ्வाट्'],
    },
  },
  {
    id: 'pros_cons',
    path: '/tools/pros-cons-wizard?module=pros-cons',
    label: 'Pros & Cons',
    icon: 'swap-horizontal',
    keywords: {
      en: ['pros and cons', 'pros cons', 'pro con'],
      hi: ['प्रोस और कॉन्स', 'प्रो कॉन'],
      ta: ['பिள्கोண्'],
      te: ['प्रोஸ் கान्ஸ்'],
      kn: ['प्रोஸ் கान्ஸ்'],
      ml: ['प्रोஸ் கान्ஸ்'],
    },
  },
  {
    id: 'public_pulse',
    path: '/tools/public-pulse',
    label: 'Public Pulse',
    icon: 'globe',
    keywords: {
      en: ['public pulse', 'pulse', 'public feedback'],
      hi: ['पब्लिक पल्स', 'जनता की बात'],
      ta: ['पब्लिक् पल्स्'],
      te: ['पब्लिक् पल्स्'],
      kn: ['पब्लिक् पल्स्'],
      ml: ['पब्लिक् पल्स्'],
    },
  },
  {
    id: 'ctt',
    path: '/tools/ctt',
    label: 'Task Tracker',
    icon: 'checkbox',
    keywords: {
      en: ['task tracker', 'ctt', 'tasks'],
      hi: ['कार्य ट्रैकर', 'कार्य'],
      ta: ['पणி ट्राक्க்'],
      te: ['టாச்க् ट्राक्க்'],
      kn: ['கர्य ட्ரाक्க்'],
      ml: ['टास्क् ट्राक्க்'],
    },
  },
  {
    id: 'consciousness_diary',
    path: '/tools/consciousness-diary',
    label: 'Consciousness Diary',
    icon: 'sparkles',
    keywords: {
      en: ['consciousness diary', 'consciousness'],
      hi: ['चेतना डायरी'],
      ta: ['விचின் நாட்குறிப்பேடு'],
      te: ['चைதன்य డైರೀ'],
      kn: ['चைதன்य ಡೈರಿ'],
      ml: ['ബोധം ഡെയറി'],
    },
  },
  {
    id: 'collaborate',
    path: '/tools/collaborate',
    label: 'Collaborate',
    icon: 'people-circle',
    keywords: {
      en: ['collaborate', 'collaboration', 'team'],
      hi: ['सहकार'],
      ta: ['குகுटு'],
      te: ['సహರಾయుత'],
      kn: ['ಸಹకाரಿಸಿ'],
      ml: ['സഹകരிಕಾണூ'],
    },
  },
  {
    id: 'daily_time_log',
    path: '/tools/daily-time-log',
    label: 'Daily Time Log',
    icon: 'stopwatch',
    keywords: {
      en: ['daily time log', 'time log', 'log my day', 'time diary'],
      hi: ['\u0926\u0948\u0928\u093f\u0915 \u0938\u092e\u092f \u0932\u0949\u0917'],
      ta: ['\u0ba4\u0bc6\u0ba8\u0bbf \u0ba8\u0bc7\u0bb0 \u0baa\u0ba4\u0bbf\u0bb5\u0bc1'],
      te: ['\u0c26\u0bc8\u0ba8\u0bbf\u0b95 \u0bb8\u092e\u092f \u0bb2\u0bbe\u0c17\u0bcd'],
      kn: ['\u0ca6\u0bc8\u0ba8\u0bbf\u0b95 \u0cb8\u092e\u092f \u0cb2\u0bbe\u0c97\u0bcd'],
      ml: ['\u0d26\u0bc8\u0ba8\u0bbf\u0b95 \u0d38\u092e\u092f \u0d32\u0d4b\u0d17\u0bcd'],
    },
  },
  {
    id: 'time_dezider',
    path: '/tools/time-dezider',
    label: 'Time Dezider',
    icon: 'hourglass',
    keywords: {
      en: ['time dezider', 'raja guru', 'day plan', 'daily guide'],
      hi: ['\u091f\u093e\u0907\u092e \u0921\u093f\u0938\u093e\u0907\u0921\u0930', '\u0930\u093e\u091c\u093e \u0917\u0941\u0930\u0941'],
      ta: ['\u091f\u0bc8\u092e\u094d \u0b9f\u0bbf\u091a\u0bc8\u0b9f\u0bb0\u094d', '\u0bb0\u093e\u091c \u0b95\u0bc1\u0bb0\u0bc1'],
      te: ['\u091f\u0bc8\u092e\u094d \u0b9f\u0bbf\u091a\u0bc8\u0b9f\u0bb0\u094d', '\u0bb0\u093e\u091c \u0b97\u0bc1\u0bb0\u0bc1'],
      kn: ['\u091f\u0bc8\u092e\u094d \u0b9f\u0bbf\u091a\u0bc8\u0b9f\u0bb0\u094d', '\u0bb0\u093e\u091c \u0c97\u0bc1\u0bb0\u0bc1'],
      ml: ['\u091f\u0bc8\u092e\u094d \u0b9f\u0bbf\u091a\u0bc8\u0b9f\u0bb0\u094d', '\u0bb0\u093e\u091c \u0d17\u0bc1\u0bb0\u0bc1'],
    },
  },
  {
    id: 'time_store',
    path: '/tools/time-store',
    label: 'Time Store',
    icon: 'cart',
    keywords: {
      en: ['time store', 'buy time', 'save time', 'delegate'],
      hi: ['\u091f\u093e\u0907\u092e \u0938\u094d\u091f\u094b\u0930', '\u0938\u092e\u092f \u0916\u0930\u0940\u0926\u094b'],
      ta: ['\u091f\u0bc8\u092e\u094d \u0b9a\u094d\u0b9f\u094b\u0bb0\u094d', '\u0ba8\u0bc7\u0bb0\u092e\u094d \u0bb5\u093e\u0b99\u094d\u0b95'],
      te: ['\u091f\u0bc8\u092e\u094d \u0bb8\u094d\u091f\u094b\u0bb0\u094d', '\u0c38\u092e\u092f\u092e\u0bc1 \u0b95\u094b\u0ba8\u094b'],
      kn: ['\u091f\u0bc8\u092e\u094d \u0bb8\u094d\u091f\u094b\u0bb0\u094d', '\u0cb8\u092e\u092f \u0b96\u0bb0\u0cbf\u0ba6\u0bb5\u0cbf'],
      ml: ['\u091f\u0bc8\u092e\u094d \u0bb8\u094d\u091f\u094b\u0bb0\u094d', '\u0bb8\u092e\u092f\u0d02 \u0d35\u093e\u0d99\u0d99\u0d41\u0d15'],
    },
  },
  {
    id: 'subscription',
    path: '/tools/subscription',
    label: 'Subscription',
    icon: 'card',
    keywords: {
      en: ['subscription', 'plans', 'upgrade', 'pricing'],
      hi: ['सदस्यता', 'मूल्य'],
      ta: ['சஂதा அट्टவணை'],
      te: ['చందಾ'],
      kn: ['चெந्நை அट्टவணை'],
      ml: ['സബ्സ्ക्ര्യ्പ्ഷൻ'],
    },
  },
];

// -----------------------------------------------------------------------
// Command verbs and stop-words — stripped before matching to isolate the
// route keyword(s). Keep in sync across languages to avoid false negatives.
// -----------------------------------------------------------------------
const COMMAND_PREFIXES: Record<SupportedLanguage, string[]> = {
  en: [
    'open', 'go to', 'go', 'navigate to', 'take me to', 'show me', 'show', 'start',
    'launch', 'visit', 'i want', 'please open', 'please go to', 'jump to',
  ],
  hi: ['खोलो', 'खोल', 'जाओ', 'पर जाओ', 'दिखाओ', 'शुरू करो', 'मुझे'],
  ta: ['திற', 'பोகு', 'பोக', 'ாக்குப्पா', 'பார்', 'பो', 'ஆரम्पி'],
  te: ['తெரு', 'இच्ల்', 'கு', 'चூप्', 'प்ரा஠ைంभिंच೑'],
  kn: ['ತೆರೆ', 'ட்ரಾಳ', 'ಮो்ப்', 'சూகக'],
  ml: ['തുറക்ள೑', 'തുറ', 'പोക்', 'അय்யோ'],
};

// -----------------------------------------------------------------------
// Normalisation helpers
// -----------------------------------------------------------------------
function normalise(text: string): string {
  return (text || '')
    .trim()
    .toLowerCase()
    .replace(/[\u200B\u200C\u200D\u2060]/g, '') // zero-width chars
    .replace(/[\u0300-\u036f]/g, '')             // combining accents
    .replace(/[!?.,;:]/g, ' ')
    .replace(/\s+/g, ' ');
}

function stripPrefixes(text: string, language: SupportedLanguage): string {
  let out = normalise(text);
  const prefixes = [
    ...COMMAND_PREFIXES.en,       // English prefixes always allowed (many Indic speakers mix)
    ...(COMMAND_PREFIXES[language] || []),
  ].map(p => normalise(p));
  // Greedy prefix strip (longest first)
  prefixes.sort((a, b) => b.length - a.length);
  for (const p of prefixes) {
    if (out.startsWith(p + ' ')) out = out.slice(p.length + 1).trim();
  }
  return out;
}

// -----------------------------------------------------------------------
// Main parser
// -----------------------------------------------------------------------
export function parseRouteCommand(
  transcript: string,
  language: SupportedLanguage = 'en',
): RouteIntent | null {
  const stripped = stripPrefixes(transcript, language);
  if (!stripped) return null;

  let best: { route: RouteDefinition; score: number; phrase: string } | null = null;

  for (const route of ROUTE_DICTIONARY) {
    const langKeys = route.keywords[language] || [];
    // Try current-language keywords first, then fall back to English
    const candidates = [
      ...langKeys.map(k => ({ k: normalise(k), lang: language })),
      ...(language !== 'en' ? route.keywords.en.map(k => ({ k: normalise(k), lang: 'en' as SupportedLanguage })) : []),
    ];
    for (const { k } of candidates) {
      if (!k) continue;
      // Prefer full-word match (boundary check) over substring
      const boundaryRegex = new RegExp(`(?:^|\\s)${escapeRegex(k)}(?:\\s|$)`);
      const isBoundary = boundaryRegex.test(stripped);
      const isSubstring = !isBoundary && stripped.includes(k);
      if (!isBoundary && !isSubstring) continue;
      const score = (isBoundary ? 100 : 50) + k.length; // longer match wins
      if (!best || score > best.score) {
        best = { route, score, phrase: k };
      }
    }
  }

  if (!best) return null;
  return {
    route: best.route,
    language,
    matchedPhrase: best.phrase,
  };
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// -----------------------------------------------------------------------
// UI helper — hint chips list
// -----------------------------------------------------------------------
export function getNavHints(language: SupportedLanguage): Array<{ id: string; label: string; icon: string }> {
  return ROUTE_DICTIONARY.map(r => ({
    id: r.id,
    label: (r.keywords[language] || r.keywords.en)[0] || r.label,
    icon: r.icon,
  }));
}
