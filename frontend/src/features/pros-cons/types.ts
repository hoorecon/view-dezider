/* Pros & Cons wizard — shared TypeScript types (extracted). */

export type Source = 'direct' | 'pro' | 'con';
export interface Factor {
  id: string; name: string; expected_value?: string | null; unit?: string | null;
  source: Source; source_option_id?: string | null; parent_id?: string | null;
  is_duplicate?: boolean;   // Step 4 — soft de-dup flag (audit history)
  display_name?: string | null;  // Step 5+ rename override; `name` stays as the original
  notation: 'mandatory' | 'optional'; priority_rank: number; std_rating: number;
  factor_type: 'subjective' | 'objective'; improvable: 'y' | 'y_bf' | 'y_both' | 'n';
  my_expectation?: string | null; others_expectations?: string | null; market_standard?: string | null;
  realistic_gap_pct: number; realistic_gap_value: number; realistic_rating?: number | null;
  weight?: number | null;   // Step 5 — sub-factor weightage (% split under its main factor)
  // Step 5 "Review & Refine Expectations" — factor metadata (parity with My Dezider).
  // Classification uses data_type: 'numeric' = Quantitative, 'text' = Qualitative
  // (we deliberately reuse data_type, NOT factor_type, which already means subjective/objective here).
  operator?: string | null;
  data_type?: 'numeric' | 'text' | null;
  data_source?: { type?: string | null; config?: Record<string, any> } | null;
}
export interface ProConItem { id: string; text: string; description?: string; importance: number; promoted_factor_id?: string | null; }
export interface OptionT { id: string; name: string; description?: string; pros: ProConItem[]; cons: ProConItem[]; }
export interface Cell { assessment_pct: number; cell_value: number; actual_value?: string | null; satisfaction_pct: number; improvement_pct: number; satisfaction_value: number; notes?: string | null; }
export interface Rollup { option_id: string; joint_score: number; overall_satisfaction_pct: number; disqualified: boolean; disqualifying_factor_ids: string[]; rank_high_to_low: number | null; }
export interface Config { mandatory_threshold_pct: number | null; max_improvement_period_months: number; std_gap: number; gap_bands?: Record<string, number>; }
export interface Guideline { rank: number; rule: string; type: string; }
export interface Analysis {
  id: string; title: string; context: string;
  life_area?: string | null;
  options: OptionT[]; factors: Factor[];
  assessments: Record<string, Record<string, Cell>>;
  config: Config; current_step: number;
  rollups?: Rollup[];
}
