# ToolMaster Handoff

> Last updated: 2026-04-14 by Claude Opus 4.6 (session: reconcile + V1 survival test — **thesis proven**)
> Status: **Active — V1 thesis cleared, V2 (offer engine) unlocked**

## Project Summary

ToolMaster is a content-addressed skill registry, loadout system, and replay-eval layer for Claude Code agents. V1 thesis proven 2026-04-14 (8/10 correct LLM-judged attribution on survival test). Current goal: V2 offer engine + PyPI publish.

## Session Log

### 2026-04-14 — V2 skill dispatch primitive shipped
- Added `toolmaster delegate <task> --loadout <name>` — calls a specialist agent (Haiku/Sonnet) with the loadout's skills loaded as the system prompt, captures output, writes a recording.
- Deliberately NOT an orchestration framework: one call, one result, no subprocess management, no planning, no multi-agent teams. Reuses `compare.py`'s LLM patterns.
- Cost estimate + confirmation gate baked in (`--dry-run`, `-y` to skip prompt).
- Smoke-tested end-to-end: Haiku 4.5 via OpenRouter with `refactor + code-review` loaded, refactored nested conditionals into early returns + `all()` form, cited "pyramid of doom" vocabulary — real specialist-skill coherence.
- 5 new tests (cost estimate, dry-run, no-API-key error, system prompt composition). Total 37/37 green.
- Design scope: `delegate.py` is ~225 lines; positioned as "skill dispatch primitive" not "multi-agent workflow" to avoid the CrewAI/AutoGen lane entirely.

### 2026-04-14 — Scout discovery expanded ~9×
- `DEFAULT_WATCH_REPOS` 5 → 19 (all Tier 2+ validated via `gh search`)
- Added GitHub Topics discovery (8 topics, 2/cycle rotation)
- Added awesome-list mining (`_extract_repos_from_awesome_list()`, 6 lists, 1/cycle)
- Added GitHub token auth (`_github_headers()` — 60→5000 req/hr)
- Per-cycle numbers: 6→53 repos searched, 10→32 skills found
- Real security findings: 1 REJECT (`competitive-ads-extractor` for ToS violation), 8 CAUTION (ComposioHQ MCP supply-chain + shell injection)
- Full catalog: `docs/discovery-sources.md`

### 2026-04-14 — Reconciliation + V1 survival test — **THESIS PROVEN**
- Discovered code is well ahead of `roadmap.md`: V1 Steps 1–4 (store, loadout, record, compare) are implemented in code but ticked as unchecked in the roadmap. Reconciled in place.
- In addition to roadmap V1 scope, there is substantial protocol/scout/sync/watcher machinery — matches `ARCHITECTURE.md` but out of scope for V1 survival.
- `tests/` was empty — created `tests/test_v1_survival.py` (13 tests, stdlib-only, all green) covering pin→resolve round-trip, loadout priority, recording, and compare plumbing.
- **V1 survival test run end-to-end** via `tests/run_v1_survival.py` with Haiku 4.5 via OpenRouter: 7 real seed skills pinned, 2 differentiated loadouts (`refactor_stack` vs `bugfix_stack`), 10 recorded tasks, blind A/B LLM judge.
- **Result: 8/10 correct attribution (80% bar cleared).** All 5 bug-fix tasks correctly routed to `bugfix_stack`; 3/5 refactor tasks routed to `refactor_stack` (one tie, one disputable bugfix call on field renaming). Per-task reasoning from judge is coherent and specific — verdicts cite actual skill names and task characteristics, not generic text.
- Full results in `docs/v1-survival-results.md`. Per `CLAUDE.md:88-90`, the V1 survival condition is met: loadout-level LLM eval produces actionable insights on real tasks. V2 (offer engine) unlocks.

(Append new sessions above this line, keep last 5 max.)

## Current State

### What Works
- Content-addressed store with SHA-256 manifests (`toolmaster/store.py`) — pin, resolve, ls, show, prefix match.
- Quality gate integrated into `pin_skill()` (`toolmaster/quality.py`) — blocks critical issues and scores < 60.
- Loadouts: create / show / list / apply / diff (`toolmaster/loadout.py`) with `toolmaster.lock` sidecar.
- Task recordings (`toolmaster/record.py`): quick_record, list, rate.
- Loadout comparison (`toolmaster/compare.py`): heuristic mode works offline; LLM mode expects `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`. Uses blind A/B randomization to reduce position bias.
- V1 tests in `tests/test_v1_survival.py` — green against a temp store.
- CLI `toolmaster` with 20 commands wired via `toolmaster/cli.py`.

### What's Broken / Blocked
- LLM judge is **untested end-to-end** in this session (no API key available). Heuristic judge works but only validates plumbing, not the thesis — the survival test below uses the heuristic path.
- No PyPI release yet (`pyproject.toml` present with `name = "toolmaster"` — availability on PyPI not yet confirmed).
- Global watcher daemon (`global_watcher.py`) is not being run; no cross-project data in `~/.toolmaster/`.

### What's Partially Done
- Scout / sync / protocol layers are implemented but unexercised in this session — they belong to V3/operational phases, not the V1 thesis test.
- **Name split resolved 2026-04-14**: everything is ToolMaster now. "Forge" was too common a name. Historical notes preserved in CLAUDE.md/roadmap.md for context; external credit ("Skill Forge") and project name ("theforge") preserved.

## Next Steps (Priority Order)

1. **Start V2 (offer engine).** Thesis is proven, gate is cleared. Build `toolmaster suggest <task>` to rank loadouts by predicted performance using recorded outcomes (roadmap V2 section). Three-offer selection: canonical / iterated / sideways. Cold start via semantic similarity until ≥50 data points per task category.
2. **Expand the survival test corpus** to 25+ diverse recordings before trusting V2 rankings. Current 8/10 attribution is significant but the sample is small; harder cases (e.g., the "rename snake_case" edge where the judge disagreed) deserve more data.
3. ~~Resolve the Forge/ToolMaster naming split~~ **DONE 2026-04-14** — unified on ToolMaster across all docs and code.
4. **Add cost estimation + result caching** to `compare.py` (roadmap Step 4 residual items) — current run used ~10 Haiku calls, fine for dev, will bite at scale.
5. **Write tests for protocol/scout/sync layers** — only the V1 thesis path is tested.
6. **Dogfood for a week** on real agent workflows before PyPI push.

## Key Decisions (Do Not Revisit)

| Decision | Why | Date |
|---|---|---|
| Kill five-slot grammar | Fights ecosystem markdown standard | 2026-04-11 |
| Kill composition operators | Skills are behavioral layers, not typed functions | 2026-04-11 |
| Decompose toolbox master into poll/sync/scout/protocol | Monolith was three systems wearing a trenchcoat | 2026-04-11 |
| Loadout is the unit of composition (not individual skills) | The thesis question is "does this stack beat that stack?" | 2026-04-11 |
| Python + stdlib-only for V1 core | Fast prototype, Haris's stack, easy PyPI | 2026-04-11 |
| Blind A/B randomization in compare | Eliminates position bias in LLM judge | (already in compare.py) |

## Architecture / File Map

```
C:\Claude\ToolMaster\
├── CLAUDE.md                  Project concept
├── ARCHITECTURE.md             Full system diagram (uses "ToolMaster" name)
├── HANDOFF.md                  ← this file
├── roadmap.md                  Phased plan — now reconciled with code reality
├── pyproject.toml              Package config
├── toolmaster/
│   ├── cli.py                  CLI entry (20 commands)
│   ├── store.py                Content-addressed store, pin/resolve
│   ├── loadout.py              Loadouts + apply + diff
│   ├── record.py               Task recordings
│   ├── compare.py              Loadout-vs-loadout judge (heuristic + LLM)
│   ├── quality.py              Skill quality gate (score ≥ 60 to pin)
│   ├── suggest.py              Task → skill recommendation
│   ├── protocol.py             Agent session lifecycle (checkin/out/used/...)
│   ├── scout.py                GitHub scout + audit + re-engineer
│   ├── sync.py                 Cross-project harvest + push
│   └── global_watcher.py       Background daemon
├── hooks/                      Claude Code lifecycle hooks
├── skills/                     Seed skills (refactor, bug-fix, code-review, ...)
├── tests/
│   └── test_v1_survival.py     V1 thesis tests (new)
└── docs/
    └── v1-survival-results.md   Results of the V1 survival test (new)
```

## State / Config

| Item | Location | Purpose |
|---|---|---|
| Global store | `~/.toolmaster/store/` | content-addressed blobs + manifests |
| Loadouts | `~/.toolmaster/loadouts/` | named skill stacks (JSON) |
| Recordings | `~/.toolmaster/recordings/` | task recordings (JSON, one per task) |
| Quality threshold | `toolmaster/quality.py` `_report()` | 60 normal, 80 strict |
| LLM model override | `TOOLMASTER_MODEL` env var | default `anthropic/claude-haiku-4.5` via OpenRouter |

## Dependencies / External Systems

- Python 3.14 confirmed working; pure stdlib for V1 core.
- OpenRouter (preferred) or Anthropic API for LLM judge — optional, heuristic fallback exists.
- No cloud / no DB for V1 — everything in `~/.toolmaster/`.

## Known Issues / Gotchas

- The quality gate will reject any skill whose SKILL.md has no `description` frontmatter field or is missing structural pieces. Seed skills in `skills/` pass. External imports may not.
- `compare_loadouts` with no API key silently falls back to heuristic — the CLI prints `Method: heuristic`, but a user running `compare` expecting LLM judgment could miss that. Confirm the `Method:` line before trusting results.
- The `toolmaster.lock` file is written to `target_dir.parent`, not `target_dir` — correct per code, but worth remembering when debugging apply.
- **Global watcher daemon is not running on this machine (confirmed 2026-04-14 from the handoff-engine session).** No `~/.toolmaster/` directory, no `watcher.pid`, no python processes. The `CLAUDE_DIR` hardcoding fix at `global_watcher.py:20` is source-correct and will take effect the next time the watcher is cold-started — there is no stale in-memory daemon to restart. If you want handoff-health monitoring live, cold-start it explicitly via `hooks/run-watcher.sh start`; do not assume it is running.

---
*This handoff follows the standard template from `C:\Claude\handoff-engine\HANDOFF_TEMPLATE.md`*
