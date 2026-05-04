# Causal Loop Diagram (CLD) Engine — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04" }

## What it is

The CLD engine helps users surface feedback loops in a problem space.
Each **node** is a variable (`Customer Acquisition Cost`,
`Aspirational Image`, `Smartphone Battery Life`, ...). Each **edge**
between two nodes carries a `polarity` (`+` reinforcing or `−` balancing)
and an optional `delay` (`yes`/`no`).

Loops are detected by traversing the directed graph and identifying
closed walks. The engine classifies each loop:

- **Reinforcing (R)**: even count of `−` edges → amplifying loop
- **Balancing (B)**: odd count of `−` edges → self-regulating loop

## Stored shape

```json
{
  "cld_id": "uuid",
  "user_id": "...",
  "title": "Why am I burning out at work?",
  "context": "...",
  "nodes": [
    {"node_id": "n1", "label": "Workload", "category": "work"},
    ...
  ],
  "edges": [
    {"from": "n1", "to": "n2", "polarity": "+", "delay": "no", "strength": 0.6, "note": "..."},
    ...
  ],
  "loops": [
    {"loop_id": "L1", "type": "R", "sequence": ["n1", "n2", "n3", "n1"], "narrative": "..."},
    ...
  ],
  "created_at": "...",
  "last_simulated": "..."
}
```

## API surface (auth)

| Method | Path | Description |
|---|---|---|
| POST | `/cld` | Create empty CLD |
| GET | `/cld` | List my CLDs |
| GET | `/cld/{id}` | Get one |
| PUT | `/cld/{id}` | Update nodes/edges |
| POST | `/cld/{id}/generate` | LLM expand: from a free-text problem statement, propose nodes + edges |
| POST | `/cld/{id}/detect-loops` | Server-side loop detection (no LLM) |
| POST | `/cld/{id}/simulate` | Run a small ODE-like simulation (no LLM) |
| POST | `/cld/{id}/narrate` | LLM produce a plain-English narrative for each loop |

## Algorithms

### Loop detection

Iterative DFS up to depth 8. Loops are normalised to start at the
lowest-id node to dedupe rotations. Loops sharing the same node-set
but different orderings are kept separate (different stories).

### Polarity classification

```
count_negative = sum(1 for e in edges if e.polarity == '-')
classification = 'B' if count_negative % 2 == 1 else 'R'
```

### Simulation

Each node has an initial value `v_0`. At each step `t`:

```
dv_i/dt = sum( w_ij * sign(polarity_ij) * f(v_j) for j in incoming)
```

where `f(x) = tanh(x)` (squashing) and `w_ij = strength`. We integrate
with Euler step `dt=0.05` for 200 steps and return per-node trajectories
for charting.

### LLM hooks

- **Generate**: prompt fed with the problem statement asks the model to
  return a JSON `{"nodes":[...], "edges":[...]}`. Validated against the
  schema before persisting.
- **Narrate**: per-loop one-shot prompt produces 2–3 sentences in the
  user's preferred language.

When the LLM budget is exhausted, both hooks return `503` (graceful
degrade); loop detection + simulation remain operational.

## UI flow

1. `/tools/cld-engine` — list of CLDs
2. `/tools/cld-detail?id=...` — graph editor (drag nodes, draw edges)
3. After save: tap Detect Loops → loops list pane
4. Tap loop → narrative drawer (uses LLM if available)

## Persistence notes

- Edge strength is normalised to `[-1, 1]`.
- Edges with `polarity="+/-"` (mixed) split into two records.
- Simulation results are NOT persisted (recomputed on demand).
