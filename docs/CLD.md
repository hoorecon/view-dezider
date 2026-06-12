# Causal Loop Diagram (CLD) Engine — Dezider

_metadata: { "version": "3.16.0", "updated": "2026-06-12" }

## What it is
Graph-based tool to surface feedback loops in a problem space. Each node is
a variable; each edge carries polarity (+ / −) and optional delay.

## Storage shape
```json
{
  "cld_id": "uuid",
  "user_id": "...",
  "title": "Why am I burning out at work?",
  "nodes": [{"node_id":"n1","label":"Workload","category":"work"}],
  "edges": [{"from":"n1","to":"n2","polarity":"+","delay":"no","strength":0.6}],
  "loops": [{"loop_id":"L1","type":"R","sequence":["n1","n2","n1"]}]
}
```

## Classification
`count_negative = sum(1 for e in edges if e.polarity == '-')`
- even → **Reinforcing (R)** — amplifies
- odd → **Balancing (B)** — self-regulates

## Algorithms
- Loop detection: iterative DFS, depth ≤ 8, canonicalised to lowest-id start.
- Simulation: Euler step, `dv_i/dt = Σ w_ij * sign(polarity) * tanh(v_j)`, `dt=0.05`, 200 steps.

## API (auth)

| Method | Path | Description |
|---|---|---|
| POST | `/cld` | create empty |
| GET | `/cld` | list |
| GET | `/cld/{id}` | one |
| PUT | `/cld/{id}` | update nodes/edges |
| POST | `/cld/{id}/generate` | LLM expand from problem statement (503 on budget) |
| POST | `/cld/{id}/detect-loops` | server-side loop detection |
| POST | `/cld/{id}/simulate` | short ODE-like simulation |
| POST | `/cld/{id}/narrate` | LLM narrate each loop (503 on budget) |

## CLD × Time Dezider integration (v3.5)

The Raja Guru engine reads the user's latest CLD to bump the score of
candidate actions that touch many graph nodes (`cld_leverage` coefficient).
An opportunity that unlocks 3+ nodes gets a +1.5 score boost, even if its
raw urgency/importance is middling — mirroring the "high-leverage action"
intuition from systems thinking.

Backlog: **Raja Guru+ AI overlay** will additionally ask the LLM to
narrate the top-scored pick *in the context of* the active CLD, e.g.
"Completing the investor deck will reduce the Anxiety loop B2, freeing your
evenings for lifestyle routines — do this before lunch."

## UI flow
1. `/tools/cld-engine` — list of CLDs
2. `/tools/cld-detail?id=...` — graph editor (drag nodes, draw edges)
3. Tap Detect Loops → loops list
4. Tap loop → narrative drawer

## Storage notes
- Edge strength normalised to `[-1, 1]`.
- Mixed-polarity edges split into two records.
- Simulation results NOT persisted (recomputed on demand).
- CLD-leverage scores live in memory (computed per Raja-Guru call).

---
## v3.16.0 — CLD status (2026-06-12)
- Engine unchanged.
- CLD Phase B (Rules engine) and Phase C (AI suggestions) remain in upcoming roadmap.
- Now that the Emergent Universal Key is topped up, the **Raja Guru + AI overlay** backlog item is unblocked and queued for next sprint.
