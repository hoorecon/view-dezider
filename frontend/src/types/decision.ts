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
  unit?: string;
  expected_value?: string | number;
  data_type?: 'numeric' | 'text';
  operator?: string;
  gap_multiplier?: number;
  parent_id?: string;
  weight?: number;
  factor_type?: 'quantitative' | 'qualitative';
  data_source?: FactorDataSource;
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
}
