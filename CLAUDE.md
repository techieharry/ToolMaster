# ToolMaster — Composable Skill Infrastructure for Claude Code Agents

## Project context

**ToolMaster** is a content-addressed skill registry, loadout system, and eval layer that sits on top of the Anthropic Agent Skills spec. It treats skill *sets* (loadouts) as the unit of composition, versioning, and evaluation — not individual skills.

Owner: Haris (Toronto). Status: V1 thesis proven (2026-04-14), entering V2 build phase.

---

## What ToolMaster is NOT

- Not an alternative skill format. Standard SKILL.md files work unchanged.
- Not a monolithic "toolbox master." Background intelligence is decomposed into specific, budgeted jobs.
- Not a composition algebra. Skills aren't functions — they're behavioral layers. ToolMaster doesn't chain them, it stacks them.

---

## Core architecture

```
Standard SKILL.md (Anthropic spec, zero changes)
        ↓
ToolMaster Registry (content-addressed, immutable snapshots, SHA-256)
        ↓
Loadouts (named, priority-ordered stacks of skill hashes)
        ↓
Replay-Eval (compare loadout A vs loadout B on historical tasks)
        ↓
Offer Engine [V2] (3 loadout options once enough data exists)
        ↓
Background Jobs [V3] (dedup, scout, iterate — separate, budgeted)
```

### 1. Content-addressed registry

Every skill version gets a frozen SHA-256 hash. Agents pin to hashes, not names. Forks create new hashes. This gives you:
- Reproducible agent runs (pin a loadout to exact hashes)
- Cache hits on stable prefixes (token savings scale with fleet size)
- Instant rollback to any prior version
- Full audit trail: which skill version produced which output

Stored locally in `~/.toolmaster/store/` (content-addressed blobs + manifests). No cloud dependency for V1.

### 2. Loadouts

A loadout is a named, priority-ordered list of pinned skill hashes. It's the unit of composition — not individual skills. Priority order resolves conflicts when multiple skills give contradictory instructions (higher priority wins, like CSS specificity).

Loadouts are themselves versioned and shareable. The key question ToolMaster answers: "does this stack produce better outcomes than that stack?"

### 3. Replay-eval

Compare loadout A vs loadout B on recorded historical tasks. Uses LLM-as-judge for scoring. Coupled to immutable versions — you can replay any historical task against any skill version (past, current, or speculative).

This is the primary differentiator vs wshobson's PluginEval, which evaluates individual skills in isolation. ToolMaster evaluates compositions over time.

### 4. Offer engine (V2)

Three-offer selection of loadouts (not individual skills) once replay data exceeds ~50 entries per task category:
- **Canonical**: highest-performing loadout for this task type
- **Iterated**: fork of canonical with speculative improvements, validated against replay logs
- **Sideways**: different loadout composition the system thinks might fit

Agent picks. The choice feeds the recommendation model. No autonomous promotion — the fleet is the filter.

### 5. Background jobs (V3)

Decomposed from the original "toolbox master" concept:
- **Dedup job**: embedding similarity scan, triggered weekly, flags semantically duplicate skills
- **Scout job**: scan starred/watched repos for skills that map to existing loadout gaps
- **Iterate job**: fork existing skills, mutate, eval against replay logs, surface as offers

Each job has its own trigger, model tier (Haiku for scouting, Sonnet for iteration), and token budget.

---

## What was killed and why

| Killed | Why |
|---|---|
| Five-slot grammar (intake/lens/core/guardrail/effect) | Fights the ecosystem. Every competitor + Anthropic spec uses freeform markdown. The constraint was creative but would require rewriting all existing skills. Available as an optional analysis lens, not a requirement. |
| Composition operators (chain/parallel/gate/override) | Skills aren't functions with typed I/O. "Chaining" two behavioral instructions is just concatenation. Operators added ceremony without substance. Replaced by priority-ordered stacks. |
| Toolbox master as single entity | Three separate systems wearing a trenchcoat. Decomposed into dedup/scout/iterate jobs with independent triggers and budgets. |
| "Parts" vocabulary | The ecosystem says "skills." Don't invent language when adoption matters. |

---

## Survival condition

V1 must prove that **loadout-level eval produces measurably better outcomes than individual skill selection.** If comparing loadouts doesn't produce actionable insights — if "stack A vs stack B" always comes back "roughly equivalent" — the whole thesis collapses.

---

## Competitive position (validated 2026-04-11)

| Primitive | Anyone else? |
|---|---|
| Content-addressed skill versions | No. Everyone is mutable CRUD + git. |
| Explicit versioned loadouts | No. Skills assigned individually everywhere. |
| Loadout-vs-loadout eval | No. wshobson evals individual skills only. |
| Three-offer selection | No. All manual or auto-trigger. |
| Data flywheel (usage → eval → offers → usage) | No. The moat is in the data, not the features. |

**Biggest threat**: Anthropic adds versioning/composition to the Agent Skills spec. Mitigation: loadout eval + offer engine require historical usage data they don't have. The data flywheel is defensible even if features are copied.

---

## Handoff obligation

This project is under `~/Documents/claude/` and inherits the global handoff mandate from the parent CLAUDE.md. You must maintain `HANDOFF.md` in this project root following `~/Documents/claude/handoff-engine/HANDOFF_TEMPLATE.md`. The handoff-reminder Stop hook will nudge you — don't ignore it.

The ToolMaster watcher itself monitors handoff health across all projects (see `check_handoff_health()` in `global_watcher.py`). It reports missing/stale handoffs in the `--status` output and in the watcher log every ~10 minutes. This is read-only visibility — enforcement is handled by the separate handoff-engine hook.

## Working style notes

- Be direct and opinionated. Kill things that deserve killing.
- Don't pad. Don't reshape three times before writing the boring version down.
- Each iteration should add a constraint that makes the previous version stronger, not replace it wholesale.
- Heavy web research = its own conversation, separate from ideation/build chats.
