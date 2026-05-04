# Regression Test Catalogue

_metadata: { "version": "3.4", "updated": "2026-05-04" }

All regression suites live in `/app/tests/` plus the legacy
`/app/backend_test_regression.py` (kept for backward-compat with CI).

## Suites

| File | Coverage | Last result |
|---|---|---|
| `tests/test_solution_matrix_orgtype.py` | Solution Matrix nested OrgType + modes + influences + templates + PDF | 61 / 61 |
| `tests/test_yoy_and_portal_smoke.py` | YoY analytics + sub-portal endpoints | 13 / 13 |
| `tests/test_hardening.py` | Security headers, body cap, gzip, audit log, DPDP, idempotency, metrics | NEW — see below |
| `backend_test_regression.py` | Auth + ACM + Solutions Store + 30+ legacy modules | 28 / 28 |

## How to run

```bash
cd /app
python tests/test_solution_matrix_orgtype.py
python tests/test_yoy_and_portal_smoke.py
python tests/test_hardening.py
python backend_test_regression.py
```

Exit code 0 = green; non-zero on any failure.

## CI integration

```yaml
# .github/workflows/api-tests.yml
steps:
  - name: Run regression
    run: |
      python tests/test_solution_matrix_orgtype.py
      python tests/test_yoy_and_portal_smoke.py
      python tests/test_hardening.py
      python backend_test_regression.py
```

## What's covered

### Solution Matrix (61 cases)
- Full nested 84-cell roundtrip
- Partial PUT preserves untouched layers
- Legacy flat payload normalises to both `individual` and `aggregate` slots
- Empty POST creates 5-slot defaults
- `matrix_mode` normalisation (case + invalid → "accurate")
- Influences (positive + negative) per-field roundtrip
- Energy<->capacity legacy mirror
- Templates list returns ≥4 covering all OrgTypes
- Template detail + 404 on unknown
- PDF Accurate-mode + Standard-mode return application/pdf
- 404 on PDF for missing entry
- Cleanup of all created entries

### YoY + Portal smoke (13 cases)
- /yoy/overall, /yoy/feedback returns 200 with k_threshold
- /yoy/tool/{slug} for known + 404 for unknown
- /p/{slug} unknown → 404
- /embed/{slug} unknown → 404
- /embed/{slug}/widget.js unknown → 404
- Auth-optional feedback POST → 404 for unknown slug (slug check first)

### Hardening (NEW — see test_hardening.py)
- Security headers present on every response
- Body > 10MB → 413
- gzip when Accept-Encoding: gzip and body > 1KB
- DPDP export round-trip
- DPDP delete-request -> cancel-delete -> status reflects state
- Audit log written on DPDP actions
- /metrics returns Prometheus text
- /health/live, /health/version respond fast

### Auth + ACM regression (28 cases)
- Register/login/me/logout/refresh
- Forgot-password rate limit
- ACM my-access shape
- Solutions Store countries + languages dict shape
- Public Pulse Phase 1+2 endpoints
- Plus a sweep of every tool's CRUD smoke

## Adding a new suite

1. Drop a new `tests/test_<area>.py` that exits with non-zero on any failure.
2. Add a row to the table above.
3. Append the run command to CI.
4. Bump the version + add a CHANGELOG line in this doc.
