/**
 * AI touchpoint feature → human-readable label map.
 *
 * Single source of truth used by:
 *   • AI Wallet — Recent activity rows + filter chips
 *   • AiConsumptionPie donut legend (/ai-wallet)
 *   • /admin/ai-touchpoints catalog
 *
 * Keys MUST match the `feature` string passed to `ai_metering.meter()` in
 * backend code. Anything missing falls back to the raw snake_case key.
 *
 * Naming convention:
 *   "<Module> · <Action>"  — short, prefix groups related touchpoints
 *   so they sort together visually.
 */
export const AI_FEATURE_LABELS: Record<string, string> = {
  // ── URL Import / Crawl
  url_import_classify: 'Import URL · Classify',
  url_import_detail:   'Import URL · Detail extract',
  url_analyze_extract: 'Import URL · Page analyze',
  url_analyze_hier_score: 'Import URL · Hierarchy score',
  url_prompt_tuning:   'Import URL · Prompt tuning',
  scrape_fetch:        'Import URL · Page fetch',
  // Deep import (two-hop)
  deep_import_hubs:        'Deep Import · Hubs',
  deep_import_links:       'Deep Import · Links',
  deep_import_constraints: 'Deep Import · Constraints',
  deep_import_consolidate: 'Deep Import · Consolidate',

  // ── Decision builder (Step 4-9)
  factor_suggestions: 'Decisions · Factor suggestions',
  prompt_autotune:    'Decisions · Prompt auto-tune',
  assist_cell:        'Decisions · AI Assist cell',
  ai_assess:          'Decisions · AI Assess',
  ai_assess_batch:    'Decisions · AI Assess (batch)',
  ai_assess_fill:     'Decisions · AI Assess (fill)',
  assess_all:         'Decisions · Assess All',
  ai_set_expectations:'Decisions · Set Expectations',
  mpps_plan:          'Decisions · MPPS plan',
  pros_cons_wizard:   'Pros & Cons · AI wizard',
  solution_finder:    'Solution Finder · AI',
  solution_finder_risks:    'Solution Finder · Risks',
  solution_finder_solutions:'Solution Finder · Solutions',
  cld_ai:             'CLD · AI Suggestions',
  screener_run:       'Investment Screener · Run',

  // ── Emotional Gatekeeper / Lifestyle
  aim_analyze:           'AIM · Analyze',
  aim_report:            'AIM · Breakthrough Report',
  eg_aim_analyze:        'AIM · Analyze',
  eg_breakthrough_report:'AIM · Breakthrough Report',
  eg_limitation_classify:'AIM · Limitation classify',
  eg_trap_analyze:       'AIM · Trap analyze',
  eg_outlet_analyze:     'Outlets Advisor · Analyze',
  outlet_analyze:        'Outlets Advisor · Analyze',
  outlet_report:         'Outlets Advisor · Breakthrough Report',

  // ── Dev / admin
  dev_test_topup: 'Dev · Test top-up',
  other: 'Other AI usage',
};

/** Lookup helper — pretty label or graceful fallback. */
export const labelForFeature = (key: string | null | undefined): string => {
  if (!key) return 'AI usage';
  return AI_FEATURE_LABELS[key] || key
    // graceful fallback: snake_case → Title Case
    .split('_').map(w => w ? w[0].toUpperCase() + w.slice(1) : w).join(' ');
};
