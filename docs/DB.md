# View Dezider Database

## Schema Overview
- `users` – accounts and roles.
- `projects` – decision projects.
- `factor_groups` – top-level factors and weights.
- `sub_factors` – internal splits per factor group.
- `gates` – hard/soft rules.
- `options` – alternatives.
- `scores` – option × sub-factor scores.
- `option_results` – computed totals, flags, disqualification.
- `audit_log` – action history.

See `/db/schema.sql` for full DDL.

## Stored Procedures
- `sp_create_project`
- `sp_add_factor_group`
- `sp_add_sub_factor`
- `sp_add_gate`
- `sp_add_option`
- `sp_set_score`
- `sp_compute_results`

Stored procedures live in `/db/procedures.sql` and are invoked by the backend via `SimpleJdbcCall`.

## Seed Data
`/db/seed.sql` inserts the “LMS Purchase” project, weights, gates, options, and sample scores.
