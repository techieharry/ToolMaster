# Offer Engine (V2)

## Status: Designed, not built. Gated on V1 proving loadout eval works.

## Mechanic

When an agent needs skills for a task, ToolMaster offers three **loadouts** (not individual skills):

1. **Canonical** — highest win rate loadout for this task type based on replay-eval data
2. **Iterated** — fork of canonical with speculative improvements, pre-validated against replay logs
3. **Sideways** — different loadout composition the system thinks might fit based on semantic similarity

## Key changes from original concept

- **Unit of selection is the loadout, not the skill.** You're choosing a stack, not a part.
- **V2, not V1.** Needs replay data (>50 entries per task category) before offers are meaningful.
- **Direct pin escape hatch.** Agents can lock to a specific loadout hash and skip the offer ceremony. Offers are the default for exploration, not a toll booth.

## Cold start strategy

Before enough replay data exists:
- Offer 1: highest-downloaded from registry (social proof)
- Offer 2: best semantic match to task description (embedding similarity)
- Offer 3: random from same category (exploration)

Graduate to canonical/iterated/sideways after N data points.

## CLI

```
toolmaster suggest <task-description>    # returns 3 loadout recommendations
toolmaster suggest --pin <hash>          # skip offers, use this loadout directly
```

## Open questions

- Selection granularity: per-task? per-session? Leaning per-task — each task may need different skills.
- Token cost of generating the sideways bet: requires understanding task semantics. Budget: one Haiku call per suggestion.
- How to measure "win rate": LLM-judge scores from replay-eval, aggregated per loadout per task category.
