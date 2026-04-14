# ToolMaster Roadmap

## Completed

- [x] Deep-dive competitor docs (Multica, LobeHub, Superpowers, wshobson/agents, Anthropic Skills)
- [x] Confirm four-primitive wedge (holds — no competitor combines all four)
- [x] Identify load-bearing primitives (immutable versions + offer engine)
- [x] Kill five-slot grammar (fights ecosystem)
- [x] Kill composition operators (skills aren't functions)
- [x] Reshape: registry + loadouts + replay-eval as V1 core
- [x] Second validate/guillotine pass on reshaped version

---

## V1 — CLI MVP: "Does this loadout beat that one?"

**Goal**: Prove that loadout-level eval produces actionable insights. Five commands, no cloud.

> **Reconciliation (2026-04-14)**: Code is well ahead of this plan. Steps 1–4 are implemented as Python modules under `toolmaster/`. CLI ships as `toolmaster`. Naming split with CLAUDE.md (old "Forge" name) resolved 2026-04-14 — everything is ToolMaster now. Survival test result: see `docs/v1-survival-results.md`.

### Step 1: Registry & Pin — ✅ DONE (code), tests added 2026-04-14

Content-addressed store under `~/.toolmaster/store/`.

- [x] Design store layout (`~/.toolmaster/store/` — blobs + manifests)
- [x] `toolmaster pin <skill-dir>` — hash a skill directory into the store
  - Walks directory, SHA-256s each file, builds manifest, stores blobs + manifest
- [x] `toolmaster resolve <hash> <target>` — reconstruct skill from store
- [x] `toolmaster ls` — lists all pinned skills with name, hash prefix, pinned_at
- [x] Tests: pin → resolve round-trip + prefix hash lookup (`tests/test_v1_survival.py`)
- [ ] Bonus: quality gate integrated into pin (`toolmaster/quality.py`, scored 0–100, threshold 60)

**Language**: Python (fast to prototype, Haris's stack). Single package, no external deps beyond stdlib for V1.

**Validate before moving on**: Pin 5 real skills from `anthropics/skills` and `obra/superpowers`. Confirm hashes are stable, resolve works, and the store doesn't bloat.

### Step 2: Loadouts — ✅ DONE (code), tests added 2026-04-14

- [x] `toolmaster loadout create <name> <hash1> <hash2> ...` — priority-ordered list
- [x] `toolmaster loadout show <name>`
- [x] `toolmaster loadout apply <name> [--target claude|agents]` — resolves into `.claude/skills/` or `.agents/skills/`, writes `toolmaster.lock` sidecar
- [x] `toolmaster loadout diff <A> <B>` — shows add/remove + priority-order changes
- [x] Loadouts stored as JSON in `~/.toolmaster/loadouts/`

**Validate before moving on**: Create two loadouts with overlapping skills, apply each, confirm agent picks up the right skills. Test priority ordering — does higher-priority skill's instruction win when two conflict?

### Step 3: Recording — ✅ DONE (code), tests added 2026-04-14

- [x] `toolmaster record -t "..." -o "..." -l <loadout> [-r 1-5]` — quick_record one-shot
- [x] `start_recording` / `stop_recording` (module API, not CLI-surfaced yet)
- [x] `toolmaster recordings` — lists all recordings
- [x] Recording JSON format: `{id, task, loadout, skill_hashes, started_at, ended_at, output, rating, status}`
- [x] `rate_recording(id, 1-5)` API (CLI exposure via `-r` on record)

**Implementation options** (pick one):
- A: Shell wrapper that captures stdin/stdout of agent session
- B: Claude Code hook (post-tool, post-response) that logs to ToolMaster
- C: Manual — user runs `toolmaster record` after the work is done

Option C shipped for V1 (`toolmaster record -t "..." -o "..." -l <loadout>`). Upgrade to B for V1.1.

**Validate before moving on**: Record 10 real task sessions across 2 different loadouts. Confirm recordings capture enough context for meaningful comparison.

### Step 4: Compare — ✅ DONE (code), tests added 2026-04-14

- [x] `toolmaster compare <A> <B>` — runs judge across all complete recordings
- [x] LLM path via OpenRouter or Anthropic direct, heuristic fallback when no API key
- [x] Blind A/B randomization per recording to reduce position bias
- [x] Output: wins_a / wins_b / ties, per-task winner + reasoning, overall winner
- [x] Judge prompt in `compare.py:112-144` — asks judge to evaluate *loadout composition*, not raw output quality
- [ ] Cost estimation before running (`~X tokens, ~$Y`) — not yet surfaced
- [ ] Result caching by `(loadoutA_hash, loadoutB_hash, recording_set_hash)` — not yet built

**Survival test run 2026-04-14 — THESIS PROVEN**: see `docs/v1-survival-results.md`. Heuristic path validated plumbing (6/10 attribution, above random); LLM path via Haiku 4.5 through OpenRouter scored **8/10 correct attribution** on 10 recordings across 2 deliberately differentiated loadouts, with coherent per-task reasoning. The survival condition in CLAUDE.md:88-90 is met.

### Step 5: Package & Ship — ⏳ PARTIAL

- [x] `pyproject.toml` present; CLI entry wired via `python -m toolmaster`
- [x] CLI entry point registered as `toolmaster` console_script (`[project.scripts]` in pyproject.toml)
- [x] **Name resolved to ToolMaster** (2026-04-14) — "Forge" was too common. All docs and code now unified.
- [ ] README with quick start (pin → loadout → record → compare)
- [ ] Publish to PyPI as `toolmaster` (check name availability)
- [ ] Test against Claude Code, Cursor, Codex skill paths
- [ ] Dogfood on own agent workflows for 1 week before announcing

---

## V2 — Offer Engine (Month 2-3)

**Gate cleared 2026-04-14**: `toolmaster compare` produced actionable LLM-judged insights (8/10 attribution on the survival run).

- [ ] Recommendation model: given a task description, rank loadouts by predicted performance using recorded outcomes
- [ ] Three-offer selection: canonical (highest win rate), iterated (forked variant), sideways (different composition)
- [ ] `toolmaster suggest <task-description>` — returns 3 loadout recommendations with reasoning
- [ ] Agent picks → choice logged → model improves
- [ ] Cold start: semantic similarity to task description when <50 data points; graduate to outcome-based ranking after

---

## V3 — Background Intelligence (Month 4-6)

**Gate**: Only start V3 if V2 offer engine measurably improves loadout selection over manual choice.

- [ ] Dedup job: embedding similarity scan across store, flag semantic duplicates, suggest merges
- [ ] Scout job: scan configured repos for new skills, evaluate fit against existing loadout gaps
- [ ] Iterate job: fork skill → mutate instructions → eval against replay logs → surface as offer candidate
- [ ] Each job: own trigger schedule, model tier (Haiku/Sonnet), token budget cap, dry-run mode

---

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-11 | Kill five-slot grammar | Fights ecosystem standard (freeform markdown). Every competitor + Anthropic spec disagrees. |
| 2026-04-11 | Kill composition operators | Skills are behavioral layers, not typed functions. Chain/parallel/gate assumes I/O that doesn't exist. |
| 2026-04-11 | Decompose toolbox master | Three separate systems (dedup, scout, iterate) with different triggers and budgets. Monolithic entity was vague and expensive. |
| 2026-04-11 | V1 = CLI, no cloud | Prove the thesis locally before adding distribution complexity. |
| 2026-04-11 | Loadout is the unit of composition | Not individual skills. The question is "does this stack beat that stack?" |
| 2026-04-11 | Python for V1 | Fast to prototype, Haris's stack, no compile step, easy PyPI distribution. |
