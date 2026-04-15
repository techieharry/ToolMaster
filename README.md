# ToolMaster

**A content-addressed skill registry for AI coding agents, with LLM-judged loadout evaluation and autonomous GitHub discovery.**

Treats skills as a measured, versioned portfolio instead of individually-selected markdown files. Pins every skill version by SHA-256, bundles them into priority-ordered *loadouts*, and uses an LLM as a blind A/B judge to rank which loadouts actually work on your historical tasks.

```
┌──────────────────────────────────────────────────────────┐
│  43 tests green  ·  8/10 LLM-judge attribution on V1     │
│  11 real production skills harvested  ·  342+ audited    │
│  Python stdlib only  ·  Zero dependencies  ·  MIT        │
└──────────────────────────────────────────────────────────┘
```

---

## The 60-second demo

```bash
git clone https://github.com/techieharry/ToolMaster.git
cd ToolMaster

# Pin some real skills into the content-addressed store
python -m toolmaster pin skills/refactor
python -m toolmaster pin skills/bug-fix
python -m toolmaster pin skills/test-generator

# Build two deliberately differentiated loadouts
python -m toolmaster loadout create refactor_stack <refactor-hash>
python -m toolmaster loadout create bugfix_stack <bug-fix-hash> <test-generator-hash>

# Ask the offer engine which loadout fits a task
python -m toolmaster offer "write a failing test for an off-by-one bug"
#   → ranks loadouts by BM25F + outcome data, returns canonical/iterated/sideways

# One-shot: offer + dispatch to a specialist agent
python -m toolmaster autopilot "refactor the long handler function"
#   → picks canonical loadout, calls Haiku 4.5 with skills loaded as system prompt,
#     returns specialist output, writes recording so future rankings learn
```

---

## Why this exists

Every agent tooling system today — Anthropic's Skills spec, wshobson/agents, obra/superpowers, Multica, LobeHub — treats skills as **individual, mutable, name-addressed assets**. You install them one at a time, match them by keyword, and evaluate them one at a time.

Nobody asks:
- *Does this stack of skills beat that stack on this type of task?*
- *Which combinations actually produce lower edit distances in practice?*
- *Can the same outcome signal drive recommendations, without relying on download counts?*

ToolMaster does.

| Primitive | ToolMaster | Anthropic Skills | wshobson/agents | obra/superpowers | Multica | LobeHub |
|---|---|---|---|---|---|---|
| Content-addressed skill versions (SHA-256) | ✅ | ❌ | ❌ | ❌ | ⚠ lockfile only | ❌ |
| Loadouts as the unit of composition | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Loadout-vs-loadout LLM eval** | ✅ 8/10 on survival test | ❌ | per-skill only | ❌ | ❌ | ❌ |
| Autonomous GitHub scout + safety audit | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cross-project data flywheel | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Skill dispatch to specialist agents (cost-reduced) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

No competitor has more than one of these. ToolMaster has all six.

---

## The V1 survival test result (2026-04-14)

The core question: does loadout-level evaluation actually produce *actionable* insight, or does it collapse to noise?

**Setup:**
- 7 real seed skills pinned from [skills/](skills/) (`refactor`, `bug-fix`, `code-review`, `data-analysis`, `document-writer`, `test-generator`, `api-integration`)
- Two deliberately differentiated loadouts: `refactor_stack` (`refactor + code-review + document-writer`) vs `bugfix_stack` (`bug-fix + test-generator + data-analysis`)
- 10 recorded tasks (5 refactor-coded, 5 bug-fix-coded)
- Blind A/B LLM judge via `anthropic/claude-haiku-4.5` through OpenRouter, position randomized per-task to eliminate bias

**Result: 8/10 correct attribution.**

- All 5 bug-fix tasks → `bugfix_stack` (5/5)
- 3/5 refactor tasks → `refactor_stack`, 1 tie, 1 defensible miss
- Per-task reasoning from the judge was specific and coherent — cited actual skill names (*"Loadout A's refactor skill directly addresses the core task..."*) and task characteristics, not generic text

Full driver: [tests/run_v1_survival.py](tests/run_v1_survival.py) · Results: [docs/v1-survival-results.md](docs/v1-survival-results.md)

---

## Architecture

```
Standard SKILL.md (Anthropic spec, zero changes)
        ↓
ToolMaster Registry — content-addressed, SHA-256, immutable versions
        ↓
Loadouts — named, priority-ordered stacks of skill hashes
        ↓
Replay-Eval — blind A/B LLM judge, loadout vs loadout, result cached
        ↓
Offer Engine (V2) — canonical / iterated / sideways ranking
        ↓
Delegate Primitive — specialist agent dispatch with pinned loadout
        ↓
Autonomous Layer — scout crawls GitHub, audits via LLM, writes proposals
```

Full diagram + data flow + model routing: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## What's in the repo

```
toolmaster/                         Python package, 14 modules, stdlib only
├── store.py                        Content-addressed SHA-256 store
├── loadout.py                      Named priority-ordered stacks + 7 agent targets
├── record.py                       Task recordings for replay-eval
├── compare.py                      Blind A/B LLM judge + cost preview + result cache
├── offer.py                        V2 offer engine (canonical/iterated/sideways)
├── delegate.py                     Skill dispatch primitive + autopilot
├── suggest.py                      Skill ranking with BM25F + performance boost
├── matcher.py                      7-signal BM25F (exact/prefix/phrase/bm25f/jaccard/fuzzy)
├── quality.py                      Skill quality gate (0-100, critical-fail on security)
├── protocol.py                     Agent session lifecycle (checkin/out/used/return)
├── scout.py                        GitHub crawl + LLM audit + re-engineer + propose
├── sync.py                         Cross-project harvest + push
├── global_watcher.py               Background daemon (poll/sync/scout scheduler)
└── cli.py                          19 commands

tests/
├── test_v1_survival.py             43 stdlib-only tests, all green
└── run_v1_survival.py              End-to-end survival driver (LLM judge)

skills/                             7 seed skills (refactor, bug-fix, ...)
hooks/                              Claude Code lifecycle hooks + daemon launcher
docs/
├── v1-survival-results.md          Full survival test output with per-task reasoning
├── discovery-sources.md            Catalog of 3-tier scout discovery pipeline
├── competitive-analysis.md         Full competitive landscape
├── immutable-parts.md              Why content-addressing is load-bearing
├── roguelike-selection.md          Design of the three-offer V2 UX
└── toolbox-master.md               V3 background job design
```

---

## Install

```bash
git clone https://github.com/techieharry/ToolMaster.git
cd ToolMaster
pip install -e .
```

Or run without install:
```bash
python -m toolmaster <command>
```

Python 3.10+. Zero runtime dependencies — `toolmaster` is pure stdlib. Tests are stdlib `unittest` (no pytest).

---

## Multi-agent target support

```bash
python -m toolmaster loadout apply refactor_stack --target claude    # .claude/skills/
python -m toolmaster loadout apply refactor_stack --target cursor    # .cursor/rules/
python -m toolmaster loadout apply refactor_stack --target codex     # .codex/skills/
python -m toolmaster loadout apply refactor_stack --target aider     # .aider/conventions/
python -m toolmaster loadout apply refactor_stack --target windsurf  # .windsurf/rules/
python -m toolmaster loadout apply refactor_stack --target continue  # .continue/context/
python -m toolmaster loadout apply refactor_stack --target agents    # .agents/skills/
```

---

## Autonomous layer (optional, requires `OPENROUTER_API_KEY`)

```bash
# Single scout cycle: crawls 19 watched repos + GitHub topics + awesome-list mining
python -m toolmaster scout

# Persistent background daemon:
# Windows:    ./hooks/run-watcher.ps1 start
# Unix/Bash:  ./hooks/run-watcher.sh  start
```

The scout fetches external skill candidates, runs a static security pre-scan (prompt injection, shell execution, credential references, obfuscation), then an LLM safety audit via Haiku, then writes `import`/`extract_techniques`/`reject` proposals to `~/.toolmaster/proposals/`. See [docs/discovery-sources.md](docs/discovery-sources.md) for the full pipeline.

---

## Status

| Phase | Status | Notes |
|---|---|---|
| V1 — CLI MVP | ✅ shipped | Store, loadouts, recording, compare. Survival test passed 8/10. |
| V2 — Offer engine | ✅ code shipped | Cold-start tested; warm-path needs accumulated data |
| V2 — Delegate primitive | ✅ shipped | Specialist agent dispatch with pinned loadout |
| V2 — Multi-agent targets | ✅ 7 agents | Claude, Cursor, Codex, Aider, Windsurf, Continue, generic |
| V2 — Scout expansion | ✅ shipped | 19 repos + topic + awesome-list mining, auth'd |
| V3 — Background jobs | 🔨 designed | Dedup, scout (built), iterate (designed) |

See [roadmap.md](roadmap.md) for details.

---

## Testing

```bash
python -m unittest tests.test_v1_survival -v
# Ran 43 tests in 1.5s — OK
```

All tests are stdlib-only and isolate to tmp directories. No network required.

---

## License

MIT — see [LICENSE](LICENSE). Built as open-source infrastructure; contributions welcome.

---

## About

Built by [Haris Yusuf](https://github.com/techieharry) in Toronto, with Claude Code (Opus 4.6 / 1M context) as the pair-programming co-author. Every commit credits both.

**The problem I had**: 12+ active projects with 20+ SKILL.md files scattered across them, zero visibility into which ones worked, which combinations worked, or which versions were "last-good" when I edited something and it got worse. Manual skill curation didn't scale past ~5 skills. I wanted a system that measures the skill portfolio the way I measure code quality — per-version, per-composition, per-outcome.

Nothing existing did that, so I built it.

**Open to roles** in AI developer tooling, agent infrastructure, LLM evaluation, and Python / system design work. Reach me via GitHub issues or the contact info on my [profile](https://github.com/techieharry).
