/**
 * Dashboard tile metadata + default layout.
 *
 * This is the single source of truth for how each dashboard tile RENDERS
 * (icon, gradient, title, subtitle, route, variant). The ORDER of sections,
 * their display NAME, and which tiles belong to which section are configurable
 * at runtime via the backend `dashboard_layout` config (Admin → Dashboard
 * Sections editor). When no server config exists, DEFAULT_LAYOUT is used.
 *
 * Visibility is still controlled separately by the ACM (`isTileOn(id)` and
 * `dash_section_<id>`); this file only governs structure + appearance.
 */

export type TileVariant = 'action' | 'colab';

export interface TileMeta {
  title: string;
  subtitle: string;
  icon: string;            // Ionicons name
  route: string;
  variant: TileVariant;
  gradient?: [string, string];  // for 'action' cards
  iconBg?: string;              // for 'colab' cards
  iconColor?: string;           // for 'colab' cards
  alwaysOn?: boolean;           // not gated by ACM isTileOn
  badgeKey?: 'inbox' | 'unread';
}

export const TILE_META: Record<string, TileMeta> = {
  // §1 Self Discovery
  pna: { title: 'My 360° Life', subtitle: 'Problems · Needs · Aspirations', icon: 'layers', route: '/tools/pna', variant: 'action', gradient: ['#4338CA', '#6366F1'] },
  gem: { title: 'GEM', subtitle: 'Goal Execution Manager', icon: 'flag', route: '/tools/gem', variant: 'action', gradient: ['#0F766E', '#14B8A6'] },

  // §2 Decision Kickstarters
  instant_dezider: { title: 'Instant Dezider', subtitle: 'Instant decision', icon: 'flash', route: '/test123', variant: 'action', gradient: ['#E91E63', '#C2185B'] },
  my_dezider: { title: 'MyDezider', subtitle: '10-step canonical', icon: 'compass', route: '/tools/dezider-list', variant: 'action', gradient: ['#6366F1', '#8B5CF6'] },
  pros_cons: { title: 'Pros & Cons', subtitle: 'Two-column starter', icon: 'git-compare', route: '/tools/pros-cons-list', variant: 'action', gradient: ['#059669', '#10B981'] },
  emotional_gatekeeper: { title: 'Emotional Gatekeeper', subtitle: 'Break loops & traps', icon: 'heart-circle', route: '/tools/emotional-gatekeeper', variant: 'action', gradient: ['#F59E0B', '#D97706'] },

  // §3 Problem Solvers
  solution_finder: { title: 'Solution Finder', subtitle: 'Concerns → RCA → Plan · ASM', icon: 'bulb', route: '/tools/solution-finder-list', variant: 'action', gradient: ['#7C3AED', '#C084FC'] },
  conflict_breaker: { title: 'The Conflict Breaker', subtitle: 'Crucial conversations', icon: 'flash', route: '/tools/conflict-breaker', variant: 'action', gradient: ['#7C2D12', '#DC2626'] },

  // §4 Goals & Manifestation
  goal_setter: { title: 'Goal Setter', subtitle: 'SMART Framework', icon: 'flag', route: '/tools/goal-setter', variant: 'action', gradient: ['#059669', '#10B981'] },
  goal_manifestation: { title: 'Manifestation', subtitle: 'CAB-FAME 7 stages', icon: 'sparkles', route: '/tools/goal-manifestation', variant: 'action', gradient: ['#7C3AED', '#9333EA'] },

  // §5 Execute & Track
  orgs: { title: 'My Organizations', subtitle: '7×7 matrix · 6 LeGs goals', icon: 'business', route: '/tools/orgs', variant: 'action', gradient: ['#4338CA', '#6366F1'] },
  values: { title: 'Values Tracker', subtitle: '8 VEALES Collaboration Principles', icon: 'shield-checkmark', route: '/tools/values', variant: 'action', gradient: ['#0EA5E9', '#0284C7'] },
  action_tracker: { title: 'Action Tracker', subtitle: 'Universal inbox', icon: 'checkmark-done-circle', route: '/tools/action-center', variant: 'action', gradient: ['#0D9488', '#0F766E'] },
  atex: { title: 'Effort Estimation', subtitle: 'ATEX · EE+MB+PB+RM=TT', icon: 'calculator', route: '/tools/atex', variant: 'action', gradient: ['#7C3AED', '#A855F7'], alwaysOn: true },
  ctt: { title: 'CTT', subtitle: 'Project tracker', icon: 'clipboard', route: '/tools/ctt', variant: 'action', gradient: ['#1E3A5F', '#2D5F8B'] },
  lifestyle_dezider: { title: 'Lifestyle Dezider', subtitle: 'Decide a change', icon: 'leaf', route: '/tools/lifestyle', variant: 'action', gradient: ['#065F46', '#059669'] },

  // §6 Reflection & Awareness
  public_pulse: { title: 'Life Mirror', subtitle: 'Self-discovery quiz', icon: 'sparkles', route: '/tools/public-pulse', variant: 'action', gradient: ['#6366F1', '#8B5CF6'] },
  outlet_analyzer: { title: 'Outlet Analyzer', subtitle: 'Coping strategies', icon: 'heart-circle', route: '/tools/eg-outlet', variant: 'action', gradient: ['#10B981', '#059669'] },
  aim_manager: { title: 'AIM Manager', subtitle: 'Addictions · Irritations', icon: 'flame', route: '/tools/eg-aim', variant: 'action', gradient: ['#F97316', '#EA580C'] },
  capabilities_index: { title: 'Capabilities & Resources Index', subtitle: 'Resource tracking', icon: 'cube', route: '/tools/tepfi', variant: 'action', gradient: ['#7C3AED', '#A855F7'] },
  lifestyle_designer: { title: 'Lifestyle Designer', subtitle: 'Design daily routine', icon: 'color-palette', route: '/tools/lifestyle-designer', variant: 'action', gradient: ['#7C2D12', '#EA580C'] },
  lifestyle_analyzer: { title: 'Lifestyle Analyzer', subtitle: 'Actual vs Planned', icon: 'analytics', route: '/tools/lifestyle-eval', variant: 'action', gradient: ['#7C3AED', '#A855F7'] },
  consciousness_diary: { title: 'Consciousness Diary', subtitle: 'Self-awareness journal', icon: 'eye', route: '/tools/consciousness-diary', variant: 'action', gradient: ['#1E1B4B', '#3730A3'] },
  unconditional_happiness: { title: 'Unconditional Happiness', subtitle: 'Celebrate · Streaks', icon: 'happy', route: '/tools/unconditional-happiness', variant: 'action', gradient: ['#EC4899', '#F472B6'] },

  // §7 Collaboration & Management
  collaboration_hub: { title: 'Collaboration Hub', subtitle: 'Group decisions · Contacts', icon: 'git-network', route: '/tools/collaborate', variant: 'action', gradient: ['#7C3AED', '#A855F7'] },
  aala: { title: 'AALA', subtitle: 'Assets & Liabilities', icon: 'wallet', route: '/tools/aala', variant: 'action', gradient: ['#0EA5E9', '#2563EB'] },
  time_dezider: { title: 'Time Intelligence', subtitle: 'Daily schedule AI', icon: 'time-outline', route: '/tools/time-dezider', variant: 'action', gradient: ['#7C3AED', '#A855F7'] },
  gem_flight: { title: 'GEM Flight Model', subtitle: 'Pilot your goals', icon: 'airplane', route: '/tools/gem-flight', variant: 'action', gradient: ['#0C1445', '#3949AB'] },
  knowledge_marketplace: { title: 'Knowledge Marketplace', subtitle: 'Publish & clone decisions', icon: 'storefront', route: '/marketplace', variant: 'action', gradient: ['#9333EA', '#A855F7'] },
  my_earnings: { title: 'My Earnings & Payouts', subtitle: 'Marketplace income · payouts', icon: 'cash', route: '/earnings', variant: 'action', gradient: ['#16A34A', '#22C55E'] },
  karma_fame: { title: 'Karma & Fame', subtitle: 'Karma points · leaderboard', icon: 'trophy', route: '/leaderboard', variant: 'action', gradient: ['#F59E0B', '#FBBF24'] },

  // §8 Solution Space
  solution_store: { title: 'Solution Store', subtitle: 'Products & services', icon: 'storefront', route: '/tools/solutions-store', variant: 'action', gradient: ['#7C3AED', '#A855F7'] },
  review_net: { title: 'Review Net', subtitle: 'Factor-wise ratings', icon: 'star', route: '/tools/review-net', variant: 'action', gradient: ['#F59E0B', '#FBBF24'] },
  deo: { title: 'DEO', subtitle: 'Import & API', icon: 'git-network', route: '/tools/deo', variant: 'action', gradient: ['#059669', '#10B981'] },
  time_store: { title: 'Time Store', subtitle: 'Buy back time', icon: 'cart-outline', route: '/tools/time-store', variant: 'action', gradient: ['#DC2626', '#EF4444'] },

  // §9 More Tools — colab strip (always-on small cards with badges)
  inbox: { title: 'Shared Inbox', subtitle: 'No pending', icon: 'mail-unread', route: '/inbox', variant: 'colab', iconBg: 'rgba(99,102,241,0.1)', iconColor: '#6366F1', alwaysOn: true, badgeKey: 'inbox' },
  notifications: { title: 'Notifications', subtitle: 'All caught up', icon: 'notifications', route: '/notifications', variant: 'colab', iconBg: 'rgba(245,158,11,0.1)', iconColor: '#F59E0B', badgeKey: 'unread' },
  analytics: { title: 'Folder Analytics', subtitle: 'Life areas', icon: 'bar-chart', route: '/analytics', variant: 'colab', iconBg: 'rgba(16,185,129,0.1)', iconColor: '#10B981' },
  // §9 More Tools — action cards
  contacts: { title: 'Contacts', subtitle: 'Manage participants', icon: 'people', route: '/tools/contacts', variant: 'action', gradient: ['#1E293B', '#475569'] },
  calendar: { title: 'Calendar', subtitle: 'Schedules & deadlines', icon: 'calendar', route: '/tools/calendar-view', variant: 'action', gradient: ['#4285F4', '#5B9EF4'] },
  ai_assistant: { title: 'AI Assistant', subtitle: 'Cross-module advisor', icon: 'chatbubble-ellipses', route: '/tools/ai-assistant', variant: 'action', gradient: ['#312E81', '#818CF8'] },
  social_learning: { title: 'Social Learning', subtitle: 'News → templates', icon: 'newspaper', route: '/tools/social-learning', variant: 'action', gradient: ['#7C3AED', '#A855F7'] },
  cld_engine: { title: 'CLD Engine', subtitle: 'Systems thinking', icon: 'git-network-outline', route: '/tools/cld-engine', variant: 'action', gradient: ['#1E40AF', '#3B82F6'] },
  subscription: { title: 'Subscription', subtitle: 'Credits & plans', icon: 'diamond-outline', route: '/tools/subscription', variant: 'action', gradient: ['#1E293B', '#334155'] },
};

export interface LayoutSection {
  id: string;
  emoji: string;
  name: string;
  tiles: string[];
}

export const DEFAULT_LAYOUT: LayoutSection[] = [
  { id: 'self_discovery', emoji: '🌌', name: 'Self Discovery', tiles: ['pna', 'gem'] },
  { id: 'decision_kickstarters', emoji: '🔮', name: 'Decision Kickstarters', tiles: ['instant_dezider', 'my_dezider', 'pros_cons', 'emotional_gatekeeper'] },
  { id: 'problem_solvers', emoji: '❤️', name: 'Problem Solvers', tiles: ['solution_finder', 'conflict_breaker'] },
  { id: 'goals_manifestation', emoji: '🎯', name: 'Goals & Manifestation', tiles: ['goal_setter', 'goal_manifestation'] },
  { id: 'execute_track', emoji: '✅', name: 'Execute & Track', tiles: ['orgs', 'values', 'action_tracker', 'atex', 'ctt', 'lifestyle_dezider'] },
  { id: 'reflection_awareness', emoji: '🪞', name: 'Reflection & Awareness', tiles: ['public_pulse', 'outlet_analyzer', 'aim_manager', 'capabilities_index', 'lifestyle_designer', 'lifestyle_analyzer', 'consciousness_diary', 'unconditional_happiness'] },
  { id: 'collaboration_mgmt', emoji: '👥', name: 'Collaboration & Management', tiles: ['collaboration_hub', 'aala', 'time_dezider', 'gem_flight', 'knowledge_marketplace', 'my_earnings', 'karma_fame'] },
  { id: 'solution_space', emoji: '🧩', name: 'Solution Space', tiles: ['solution_store', 'review_net', 'deo', 'time_store'] },
  { id: 'more_tools', emoji: '🧰', name: 'More Tools', tiles: ['inbox', 'notifications', 'analytics', 'contacts', 'calendar', 'ai_assistant', 'social_learning', 'cld_engine', 'subscription'] },
];

export const chunk = <T,>(arr: T[], size: number): T[][] => {
  const out: T[][] = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
};
