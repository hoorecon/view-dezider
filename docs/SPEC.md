# View Dezider – Product & Domain Spec

## Purpose
View Dezider evaluates irreversible strategic decisions by scoring options against weighted factors and gate rules.

## Personas
- **Admin**: defines projects, weights, gates, and options.
- **Member**: scores options and reviews results.

## Core Entities
- **Project**: container for decision work.
- **Factor Group**: top-level criteria (1–8) with overall weight.
- **Sub-factor**: nested criteria (1.1, 1.2…) with internal split totaling 100.
- **Gate**: rules to qualify/disqualify options.
- **Option**: alternatives to evaluate.
- **Score**: 0–10 value per option × sub-factor.

## Decision Engine
1. Apply **Hard Gates** (fail → DISQUALIFIED).
2. Apply **Soft Gates**:
   - `PENALTY_POINTS` subtracts points.
   - `CAP_PERCENT` caps score.
   - `FLAG_ONLY` appends a warning.
3. Compute weighted totals (factor group weight × sub-factor split × score).
4. Rank and recommend highest scoring non-disqualified option.

## MVP Scope
- CRUD: projects, factor groups, sub-factors, gates, options, scores.
- Results: disqualified list, score breakdown, ranking, JSON export.
- Audit trail for key actions.
