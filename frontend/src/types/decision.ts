// Shared types for the PRR Decision system

export interface FactorDataSource {
  type: 'webhook' | 'web_surf' | 'ai_llm' | 'decision_link';
  config: {
    url?: string;          // For webhook
    headers?: string;      // For webhook (JSON string)
    search_query?: string; // For web_surf
    prompt?: string;       // For ai_llm
    // ── Dependent Decision link (decision_link) ──
    linked_decision_id?: string;
    linked_module?: string;          // 'mydezider' | 'pros_cons'
    linked_option_id?: string;
    linked_option_name?: string;
    linked_title?: string;
    metric?: 'option_worth' | 'top_score';
    refresh?: 'auto' | 'manual';
    link_mode?: 'factor_only' | 'factor_and_option';
  };
  last_fetched?: string;   // ISO timestamp
  last_value?: string;     // Last fetched value
}

export interface Factor {
  id: string;
  name: string;
  category: 'primary' | 'secondary';
  rating: number;
  order: number;
  // ── Standard variable identifier (June 2026) ──
  // Auto-assigned label like "f1", "f2" (see assignVariableIds). Referenced
  // by editable dependency formulas on the Decision.
  variable_id?: string;
  unit?: string;
  expected_value?: string | number;
  data_type?: 'numeric' | 'text';
  operator?: string;
  gap_multiplier?: number;
  parent_id?: string;
  weight?: number;
  factor_type?: 'quantitative' | 'qualitative';
  data_source?: FactorDataSource;
  // Option-Bank join key (template sub-factor id) — must survive saves
  source_sub_id?: string;
  // ── Dynamic UI objects (v2) ──
  // Parent-level widget: checkbox (multi) | radio | dropdown | listbox | undefined (= classic input)
  ui_object?: 'checkbox' | 'radio' | 'dropdown' | 'listbox' | string;
  // Child column role: 'value' (selectable choice — no 100% split), 'sub' (classic weighted), 'dependent' (optional refiner)
  role?: 'value' | 'sub' | 'dependent' | string;
  linked_value?: string;            // dependent → parent value name that reveals it
  default_operator?: string;        // pre-selected operator (user-overridable)
  default_expected?: string | number; // pre-filled expected (user-overridable)
  // ── Nested Factor Group (max 3 levels; June 2026) ──
  // Path from root group → sub-group → sub-sub-group. Used ONLY by
  //   Step 2 (Define Factors)  and  Step 7 (Assessment)
  // to render collapsible sections. Steps 3, 4, 5, 6 treat factors as flat.
  // Example: ["Cash Transactions", "Cash Deposit"]
  group_path?: string[];
}

export interface OptionAssessment {
  factor_id: string;
  percentage: number;
  unit_value?: string;
  actual_value?: number;
  assessment_mode?: 'L' | 'M' | 'H' | 'custom';
}

export interface DecisionOption {
  id: string;
  name: string;
  assessments: OptionAssessment[];
  worth_percentage: number;
  solution_id?: string;  // Links to Solutions Store for auto-populated data
  source?: 'ai' | 'store' | 'manual';  // provenance (Find My Best Options)
  ai_rationale?: string;               // one-line why this option fits
  price_range?: string;                // store item price badge
  rating?: number;                     // store item avg rating badge
  sf_ref?: { entry_id: string; label?: string };  // inserted from a Solution Finder SMART Goal
  description?: string;                // optional 2-3 line blurb shown in Step 6 & Decider Apps
}

// A single AI/Store suggestion returned by POST /api/ai/find-best-options
export interface BestOptionSuggestion {
  name: string;
  ai_rationale?: string;
  source?: 'ai' | 'store';
  solution_id?: string;
  price_range?: string;
  rating?: number;
  // Per-factor estimated/known actual values (Store data or AI estimate)
  factor_values?: { factor_id: string; value: number | string }[];
}

export interface MPPSActionItem {
  assignee_name: string;
  assignee_email: string;
  assignee_mobile: string;
  task: string;
  deadline?: string;
}

export interface MPPSImprovement {
  factor_id: string;
  original_percentage?: number;
  projected_percentage?: number;
  delta_percentage?: number;
  expected_value?: string;
  expected_unit?: string;
  improvement_plan: string;
  tepfi_elements?: string[];
  tepfi_layer?: 'self' | 'micro' | 'macro';
  action_items?: MPPSActionItem[];
}

export interface Decision {
  id: string;
  title: string;
  context: string;
  factors: Factor[];
  options: DecisionOption[];
  chosen_option_id: string | null;
  decision_case: string | null;
  notes: string;
  rating_gap_multiplier: number;
  mpps_option_id?: string;
  mpps_improvements?: MPPSImprovement[];
  mpps_projected_worth?: number;
  mpps_timeframe?: string;
  mpps_by_option?: Record<string, MPPSImprovement[]>;
  life_area?: string;
  decision_type?: string;
  implementation_review_date?: string;
  final_choice_reason?: string;
  final_choice_decided_at?: string;
  status: string;
  folder?: string;
  reflection?: string;
  final_notes?: string;
  // 'app' = Decider App / Finder clone (enables dynamic UI-object config in Step 2)
  decider_kind?: 'app' | 'template' | string;
  // ── Equal Weightage mode (June 2026) ──
  // When true, Step 4 uses flat weights (Mandatory/A=20, Optional/B=10) and
  // ignores rating_gap_multiplier + Realistic Gap.
  equal_weightage?: boolean;
  // ── Editable dependency formulas ──
  formulas?: DecisionFormula[];
}

export interface DecisionFormula {
  id: string;
  target: string;       // e.g. "f7"
  expression: string;   // e.g. "f1 * (f2/100) * f3 * f6 / f5"
  scope?: 'per_option' | 'cross_option';   // default: per_option
  description?: string;
}
