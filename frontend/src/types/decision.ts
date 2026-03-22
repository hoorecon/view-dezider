// Shared types for the PRR Decision system

export interface FactorDataSource {
  type: 'webhook' | 'web_surf' | 'ai_llm';
  config: {
    url?: string;          // For webhook
    headers?: string;      // For webhook (JSON string)
    search_query?: string; // For web_surf
    prompt?: string;       // For ai_llm
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
  life_area?: string;
  decision_type?: string;
  status: string;
  folder?: string;
  reflection?: string;
  final_notes?: string;
}
