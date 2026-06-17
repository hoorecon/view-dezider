/**
 * Tenses & Feels coaching content — user-editable.
 * Replace `verbatim_*` strings with your full coaching narrative from
 * 'Tenses & Feels - DoD.pdf'. The UI renders whatever you paste here.
 *
 * Structure:
 *   - 12 emotions in the framework (Past / Future / Present-Self / Present-Others)
 *   - Each emotion has: title, narrative_paraphrase, power_statement,
 *     instruction_for_user, resolution_quote
 *   - 3 healing feelings (Gratefulness, Faith, Happily Active)
 */

export type TenseCode = 'past' | 'future' | 'present';
export type EmotionCategory = 'self_emotional' | 'self_mental' | 'others_yours' | 'others_theirs' | 'none';

export interface EmotionDef {
  code: string;
  label: string;
  short: string;          // 1-line definition
  tense: TenseCode;
  polarity: 'negative' | 'positive';
  category: EmotionCategory;
  color: string;
  narrative_paraphrase: string;
  power_statement: string;       // short user-quotable affirmation
  instruction_for_user: string;  // what user is asked to do
  resolution_quote: string;      // healing principle (paraphrased)
  healing_feeling: 'gratefulness' | 'faith' | 'happily_active';
  // PASTE_VERBATIM_HERE — set this to your full coaching script for this emotion,
  // it will render in the dedicated 'Coach Script' tab inside the emotion card.
  verbatim_script?: string;
}

// ─── PAST ─────────────────────────────────────────────────────────────
export const PAST_EMOTIONS: EmotionDef[] = [
  {
    code: 'clinging', label: 'Clinging', short: "Can't let go of a bad past experience",
    tense: 'past', polarity: 'negative', category: 'none', color: '#DC2626',
    narrative_paraphrase: 'A bad experience from the past — recent or long ago — that you cannot still forget.',
    power_statement: "Irrespective of my reactions, the reality is fixed. I accept the unchangeable.",
    instruction_for_user: 'Bring up one bad experience from your past you have not let go yet. Close your eyes and feel it for 30 seconds.',
    resolution_quote: "Accept the Unchangeable and choose the response most appropriate to the situation — instead of reacting with whatever you feel like.",
    healing_feeling: 'gratefulness',
  },
  {
    code: 'longing', label: 'Longing', short: "Still longing for a good past you've lost",
    tense: 'past', polarity: 'positive', category: 'none', color: '#F97316',
    narrative_paraphrase: 'A good experience from the past you cannot still forget — and are still longing for.',
    power_statement: "Anything can be taken away at any time, in any way. I'm grateful it lasted as long as it did.",
    instruction_for_user: 'Bring up one good experience from your past for which you are still longing. Close your eyes for 30 seconds.',
    resolution_quote: "Life and everything we experience is temporary. Thank life for blessing you with that beautiful experience instead of mourning its absence.",
    healing_feeling: 'gratefulness',
  },
];

// ─── FUTURE ───────────────────────────────────────────────────────────
export const FUTURE_EMOTIONS: EmotionDef[] = [
  {
    code: 'fear', label: 'Fear', short: 'Fearful something negative may happen',
    tense: 'future', polarity: 'negative', category: 'none', color: '#7C3AED',
    narrative_paraphrase: 'Fear about the future that something negative may happen.',
    power_statement: "As per Nature's Law, fear attracts what I don't want. I acknowledge it and take constructive action.",
    instruction_for_user: 'Bring up one possible bad experience that can happen in your future about which you are fearful. Close your eyes for 30 seconds.',
    resolution_quote: "Acknowledge the Fear without resistance and take 'Consistently Constructive' actions with Complete Conviction (CCCC). If you must imagine, IMAGINE POSITIVELY.",
    healing_feeling: 'faith',
  },
  {
    code: 'anxiety', label: 'Anxiety / Desperation', short: 'Desperate for a positive future',
    tense: 'future', polarity: 'positive', category: 'none', color: '#8B5CF6',
    narrative_paraphrase: 'Anxiety or desperation about the future that some positive thing must happen.',
    power_statement: "As per Nature's Law, anxiety chases away what I desperately want. I acknowledge it and act with faith.",
    instruction_for_user: 'Bring up one possible good experience that you desperately want in your future. Close your eyes for 30 seconds.',
    resolution_quote: "Acknowledge the Anxiety without resistance and take 'Consistently Constructive' actions with Complete Conviction (CCCC). When you imagine, IMAGINE POSITIVELY.",
    healing_feeling: 'faith',
  },
];

// ─── PRESENT · Self · Emotional ───────────────────────────────────────
export const PRESENT_SELF_EMOTIONAL: EmotionDef[] = [
  {
    code: 'anger', label: 'Anger', short: 'You see others as the cause',
    tense: 'present', polarity: 'negative', category: 'self_emotional', color: '#EF4444',
    narrative_paraphrase: 'Anger arises when you perceive other person or situation as the reason for your disappointment or failure.',
    power_statement: "Even if it wasn't my fault, I take 100% responsibility for the lesson — that's where my power lives.",
    instruction_for_user: 'Bring up one person you are so angry with right now. Close your eyes and feel it for 30 seconds.',
    resolution_quote: "Assume 100% responsibility (just for self-empowerment) and find the precautionary step you could have taken. Transform anger into intense commitment to apply that life lesson.",
    healing_feeling: 'happily_active',
  },
  {
    code: 'sadness', label: 'Sadness', short: 'You see yourself as the cause',
    tense: 'present', polarity: 'negative', category: 'self_emotional', color: '#3B82F6',
    narrative_paraphrase: 'Sadness arises when you perceive yourself as the reason for your disappointment or failure — hidden anger on your own self.',
    power_statement: "I forgive myself for any ignorance or incapability. The lesson is the gift.",
    instruction_for_user: 'Bring up one problem that is making you sad. Close your eyes for 30 seconds.',
    resolution_quote: "Find the precautionary step that could have avoided this. Transform sadness into intense commitment to apply that life lesson. Self-forgiveness heals.",
    healing_feeling: 'happily_active',
  },
];

// ─── PRESENT · Self · Mental ──────────────────────────────────────────
export const PRESENT_SELF_MENTAL: EmotionDef[] = [
  {
    code: 'over_cautious', label: 'Over-Cautiousness / Urgency (Stress)', short: "Restless to get from where you are to where you want to be",
    tense: 'present', polarity: 'negative', category: 'self_mental', color: '#F59E0B',
    narrative_paraphrase: "You are at Point A but want to be at Point B, and you are restless and impatient about the journey. That's 'Responsibly Urgent' overdone — stress.",
    power_statement: "I am happily active in the present — that's where Point B actually approaches me from.",
    instruction_for_user: 'Notice one area where stress is pushing you to skip the present. Sit with it for 30 seconds.',
    resolution_quote: "Be Happily Active in the Present — that is the bridge from Point A to Point B.",
    healing_feeling: 'happily_active',
  },
  {
    code: 'over_careless', label: 'Over-Carelessness / Complacency', short: 'Boredom and least-bothered-ness',
    tense: 'present', polarity: 'negative', category: 'self_mental', color: '#CA8A04',
    narrative_paraphrase: "Opposite of stress — complacency WITHOUT responsibility. Simply careless and least bothered.",
    power_statement: "I choose engagement with responsibility — that's real contentment, not numbness.",
    instruction_for_user: 'Notice one area you have been ignoring or dismissing. Sit with it for 30 seconds.',
    resolution_quote: "True complacency requires responsibility to protect what you have accomplished. Engage with the present.",
    healing_feeling: 'happily_active',
  },
];

// ─── PRESENT · Others · Triggers from your side ────────────────────────
export const PRESENT_OTHERS_YOURS: EmotionDef[] = [
  {
    code: 'jealousy', label: 'Jealousy on Others', short: 'Pain when on-par/below others surpass you',
    tense: 'present', polarity: 'negative', category: 'others_yours', color: '#16A34A',
    narrative_paraphrase: 'Pain when others whom you consider on-par or below you excel in an area where you lack capability, resources, or success.',
    power_statement: "Their success is proof it is possible. I focus on my own next step.",
    instruction_for_user: 'Bring up one person who triggers jealousy. Close your eyes for 30 seconds.',
    resolution_quote: "Convert the comparison into inspiration. Find the specific capability or resource you can build next.",
    healing_feeling: 'happily_active',
  },
  {
    code: 'disgraceful', label: 'Treating Others Disgracefully', short: 'Urge to belittle someone below your self-identity',
    tense: 'present', polarity: 'negative', category: 'others_yours', color: '#0EA5E9',
    narrative_paraphrase: "Subtle pain of not being able to accept someone you consider below you to deal equally with you in a common situation.",
    power_statement: "Every person carries a story I have not seen. I choose dignity for them — and for myself.",
    instruction_for_user: 'Recall one moment you belittled someone (even subtly). Close your eyes for 30 seconds.',
    resolution_quote: "Self-identity that needs others to be 'below' is fragile. True confidence treats every person with equal dignity.",
    healing_feeling: 'happily_active',
  },
];

// ─── PRESENT · Others · Triggers from their side ───────────────────────
export const PRESENT_OTHERS_THEIRS: EmotionDef[] = [
  {
    code: 'aggression', label: 'Aggression on Enemies', short: 'Rage when you think of your enemies',
    tense: 'present', polarity: 'negative', category: 'others_theirs', color: '#991B1B',
    narrative_paraphrase: "Accumulated or intensified state of Anger that explodes into rage whenever you think of your enemies.",
    power_statement: "I redirect the rage energy into building, not destroying.",
    instruction_for_user: 'Bring up one enemy. Close your eyes for 30 seconds.',
    resolution_quote: "Aggression is just intensified anger. The same anger-resolution practice applies — extract the lesson, take constructive action.",
    healing_feeling: 'happily_active',
  },
  {
    code: 'heartbroken', label: 'Heartbroken on Betrayals', short: 'Depression when you think of cheaters',
    tense: 'present', polarity: 'negative', category: 'others_theirs', color: '#7E22CE',
    narrative_paraphrase: "Accumulated or intensified state of Sadness — explodes into depression at times when you think of those who betrayed you.",
    power_statement: "My heart heals. The betrayal taught me discernment.",
    instruction_for_user: 'Bring up one person who betrayed you. Close your eyes for 30 seconds.',
    resolution_quote: "Heartbreak is intensified sadness. Apply the sadness-resolution practice with self-forgiveness for trusting blindly.",
    healing_feeling: 'happily_active',
  },
];

export const ALL_EMOTIONS: EmotionDef[] = [
  ...PAST_EMOTIONS,
  ...FUTURE_EMOTIONS,
  ...PRESENT_SELF_EMOTIONAL,
  ...PRESENT_SELF_MENTAL,
  ...PRESENT_OTHERS_YOURS,
  ...PRESENT_OTHERS_THEIRS,
];

export const HEALING_FEELINGS = [
  { code: 'gratefulness',   label: 'Being Grateful for your Past',          color: '#F59E0B', icon: 'heart' },
  { code: 'happily_active', label: 'Happily Active in the Present',         color: '#10B981', icon: 'sunny' },
  { code: 'faith',          label: 'Complete Faith on your Future',         color: '#6366F1', icon: 'compass' },
];

export const TENSES_FEELS_INTRO = {
  welcome: "Welcome. As Emotional Freedom is our base, let's have a quick overview on Emotions.",
  definition: 'Emotion = e-Motion = Energies in Motion. They are the juicy, bodily reflection of thoughts.',
  pain_definition: "For simplicity, we group all negative emotions under one word: 'Pain'. Now let's dissect it.",
  pain_breakdown: 'Pain occurs about 3 things: the Past, the Future, and sometimes the Present.',
  estimated_minutes: 35,
};

export const TENSES_FEELS_LIFE_AREAS = [
  { code: 'holistic_health', label: 'Holistic Health', sub_areas: ['Physical', 'Mental', 'Emotional'] },
  { code: 'knowledge_skills', label: 'Knowledge & Skills', sub_areas: ['Knowledge', 'Skills'] },
  { code: 'relationships', label: 'Relationships', sub_areas: ['Self', 'Parents', 'Siblings', 'Spouse', 'Children', 'Relatives', 'Colleagues', 'Friends', 'Mentors', 'Life Coaches', 'Spiritual Guru', 'Divine'] },
  { code: 'finance', label: 'Finance', sub_areas: [] },
  { code: 'asset', label: 'Asset', sub_areas: ['Moveable (vehicles, things)', 'Immovable (land, building)', 'Intellectual'] },
  { code: 'career_business', label: 'Career / Business', sub_areas: [] },
  { code: 'fame', label: 'Fame / Recognition', sub_areas: [] },
  { code: 'leisure', label: 'Leisure / Recreation', sub_areas: [] },
  { code: 'contribution', label: 'Contribution / Service', sub_areas: [] },
  { code: 'spirituality', label: 'Spirituality', sub_areas: [] },
];
