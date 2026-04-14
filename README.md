# ToolMaster

> **Content-addressed skill registry + loadout system + replay-eval layer for Claude Code agents.**
> Turns skills from individually-selected markdown files into a measured, versioned, composable portfolio with a data flywheel.

**Status:** V1 thesis proven (2026-04-14) · V2 offer engine built · Private beta · Not yet published

---

## What this is (in one paragraph)

Every agent tooling system today — Claude Code native, wshobson/agents, obra/superpowers, Anthropic's Skills spec, Multica, LobeHub — treats skills as **individual, mutable, name-addressed assets**. You manually attach them, or you keyword-match them, and you evaluate them one at a time. Nobody asks "does this *stack of skills* beat that *stack of skills* on this task?" because nobody has the primitives to answer it. ToolMaster does. It pins every skill version by SHA-256 (so you can roll back, audit, and diff), bundles them into named loadouts as the unit of composition, eval-judges loadout-vs-loadout with an LLM as blind A/B judge on recorded tasks, and offers the agent three ranked loadouts per task (canonical / iterated / sideways) so every selection is a training signal.

---

## The gap it fills

| Primitive | ToolMaster | Anthropic Skills | wshobson/agents | obra/superpowers | Multica | LobeHub |
|---|---|---|---|---|---|---|
| Content-addressed skill versions | ✅ | ❌ | ❌ | ❌ | ⚠ lockfile only | ❌ |
| Loadouts as unit of composition | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Loadout-vs-loadout LLM eval** | ✅ **proven 8/10** | ❌ | ❌ (per-skill only) | ❌ | ❌ | ❌ |
| Autonomous scout + audit + propose | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cross-project data flywheel | ✅ (spinning) | ❌ | ❌ | ❌ | ❌ | ❌ |

No competitor has more than one of these. ToolMaster has all five.

---

## The flywheel

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  AGENTS BUILD SKILLS  ──────────►  harvester                     │
│                                      │                           │
│                                      ▼                           │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                  GLOBAL STORE (~/.toolmaster/)          │     │
│  │                                                         │     │
│  │   store/blobs        SHA-256 content-addressed files    │     │
│  │   store/manifests    skill versions (hash → files)      │     │
│  │   loadouts           named priority-ordered stacks      │     │
│  │   recordings         task outcome data                  │     │
│  │   proposals          scout-audited external imports    │     │
│  └────────┬────────────────────────────────┬───────────────┘     │
│           │                                │                     │
│           ▼                                ▼                     │
│    LLM-judge                          scout                     │
│    compares                           scans GitHub               │
│    loadout vs                         audits for safety          │
│    loadout on                         re-engineers weak tools    │
│    real tasks                         proposes imports           │
│           │                                │                     │
│           └──────────────┬─────────────────┘                     │
│                          ▼                                       │
│               OFFER ENGINE (V2)                                   │
│                                                                  │
│     canonical    ← top-ranked loadout by description + outcome  │
│     iterated     ← canonical's evolved cousin (swap tweak)      │
│     sideways     ← compositionally different option (explore)  │
│                                                                  │
│     AGENT PICKS ONE  ──────►  pick logged  ──────►  feeds       │
│                                                       rankings   │
│                                                       next time  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

The usage → eval → offers → usage cycle is the moat. Features copy in weeks; per-user historical outcome data does not.

---

## V1 survival test result (2026-04-14)

The roadmap's V1 gate was: *does loadout-level eval produce actionable insights on real tasks, or is it noise?*

**Setup:**
- 7 real seed skills pinned from [skills/](skills/) (refactor, bug-fix, code-review, data-analysis, document-writer, test-generator, api-integration)
- Two deliberately differentiated loadouts: `refactor_stack` (refactor + code-review + document-writer) vs `bugfix_stack` (bug-fix + test-generator + data-analysis)
- 10 recorded tasks (5 refactor-coded, 5 bug-fix-coded)
- Blind A/B LLM judge via Haiku 4.5 through OpenRouter, with position randomization

**Result:** **8/10 correct attribution.**
- All 5 bug-fix tasks → `bugfix_stack` (5/5)
- 3/5 refactor tasks → `refactor_stack`, 1 tie, 1 defensible miss (judge called "rename snake_case fields" a testing task rather than a refactoring task — debatable, not wrong)
- Per-task reasoning from judge was specific and coherent — cited actual skill names and task characteristics, not generic text

Full driver: [tests/run_v1_survival.py](tests/run_v1_survival.py) · Results: [docs/v1-survival-results.md](docs/v1-survival-results.md)

Per [CLAUDE.md:88-90](CLAUDE.md), the survival condition is met. **V2 is unlocked.**

---

## Quick start

### Install
```bash
git clone https://github.com/techieharry/ToolMaster.git
cd ToolMaster
pip install -e .
# or: python -m toolmaster <cmd>
```

### Pin a skill, build a loadout, compare against another
```bash
# 1. Pin skills into the content-addressed store
toolmaster pin skills/refactor
toolmaster pin skills/code-review
toolmaster pin skills/bug-fix
toolmaster pin skills/test-generator

# 2. Create two differentiated loadouts
toolmaster loadout create refactor_stack <refactor-hash> <code-review-hash>
toolmaster loadout create bugfix_stack   <bug-fix-hash>  <test-generator-hash>

# 3. Record some tasks (minimally)
toolmaster record -t "refactor the long handler" -o "done" -l refactor_stack
toolmaster record -t "fix the null pointer crash" -o "done" -l bugfix_stack

# 4. Compare (heuristic if no API key, LLM if OPENROUTER_API_KEY is set)
toolmaster compare refactor_stack bugfix_stack

# 5. V2 offer engine — ask for the best loadout for a task
toolmaster offer "refactor the checkout flow to reduce nesting"
```

### Apply a loadout to your agent
```bash
# ToolMaster supports 7 agent targets out of the box
toolmaster loadout apply refactor_stack --target claude      # .claude/skills/
toolmaster loadout apply refactor_stack --target cursor      # .cursor/rules/
toolmaster loadout apply refactor_stack --target codex       # .codex/skills/
toolmaster loadout apply refactor_stack --target aider       # .aider/conventions/
toolmaster loadout apply refactor_stack --target windsurf    # .windsurf/rules/
toolmaster loadout apply refactor_stack --target continue    # .continue/context/
toolmaster loadout apply refactor_stack --target agents      # .agents/skills/
```

### Autonomous acquisition layer (optional, requires `OPENROUTER_API_KEY`)
```bash
# Scout scans a curated repo list, audits each external skill through
# a static pre-scan + LLM safety audit, and writes import/extract proposals
toolmaster scout

# Persistent background watcher: polls all projects, harvests new skills,
# pushes digests, runs scout cycles
./hooks/run-watcher.ps1 start          # Windows (PowerShell)
./hooks/run-watcher.sh start           # Unix/Git Bash
```

---

## Repository layout

```
ToolMaster/
├── toolmaster/                  # Python package
│   ├── store.py                 # Content-addressed SHA-256 store
│   ├── loadout.py               # Named priority-ordered skill stacks + 7 agent targets
│   ├── record.py                # Task recordings for replay-eval
│   ├── compare.py               # Blind A/B LLM judge + cost preview + result cache
│   ├── offer.py                 # V2 offer engine (canonical/iterated/sideways)
│   ├── suggest.py               # BM25F skill ranking with performance boost
│   ├── matcher.py               # 7-signal BM25F ranking (exact/prefix/phrase/bm25f/jaccard/fuzzy)
│   ├── quality.py               # Skill quality gate (0-100 score, critical-issue fail)
│   ├── protocol.py              # Agent session protocol (checkin/checkout/used/created)
│   ├── scout.py                 # GitHub scout + LLM audit + re-engineer + propose
│   ├── sync.py                  # Cross-project harvest + push
│   ├── global_watcher.py        # Background daemon (poll/sync/scout scheduler)
│   ├── trust.py                 # Trust filter for external repos
│   ├── cli.py                   # CLI entry (17 commands)
│   └── __main__.py              # python -m toolmaster
├── tests/
│   ├── test_v1_survival.py      # 24 stdlib-only tests covering V1 + V2
│   └── run_v1_survival.py       # End-to-end survival driver (LLM judge)
├── hooks/
│   ├── run-watcher.ps1          # Windows daemon launcher (pythonw detached)
│   ├── run-watcher.sh           # Unix daemon launcher
│   ├── session-start.sh         # Notification hook: auto-checkin
│   ├── session-end.sh           # Stop hook: auto-return + archive
│   └── pre-write-check.sh       # PreToolUse hook: SKILL.md guard
├── skills/                      # Seed skills (refactor, bug-fix, code-review, ...)
├── docs/
│   ├── v1-survival-results.md   # Full survival test output with per-task judge reasoning
│   ├── competitive-analysis.md  # Full competitive landscape
│   ├── immutable-parts.md       # Why content-addressing is load-bearing
│   ├── roguelike-selection.md   # Design of the three-offer V2 UX
│   └── toolbox-master.md        # V3 background job design (dedup/scout/iterate)
├── CLAUDE.md                    # Project concept + decisions + survival condition
├── ARCHITECTURE.md              # Full system diagram + data flow + model routing
├── HANDOFF.md                   # Session continuity (for future agents)
├── roadmap.md                   # V1 (done) / V2 (offer engine built) / V3 (planned)
├── TOOLMASTER_AGENT_PROMPT.md   # Prompt distributed to agents in each project
└── pyproject.toml               # Package config (name="toolmaster")
```

---

## Architecture at a glance

```
Standard SKILL.md (Anthropic spec, zero changes)
        ↓
ToolMaster Registry (content-addressed, immutable, SHA-256)
        ↓
Loadouts (named, priority-ordered stacks of skill hashes)
        ↓
Replay-Eval (blind A/B LLM judge, loadout vs loadout)
        ↓
Offer Engine [V2] ← YOU ARE HERE
        ↓
Background Jobs [V3] (dedup + scout + iterate)
```

Full architecture with model routing, watcher schedule, and security layers: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## What's proven, what isn't

**Proven:**
- End-to-end pipeline runs on real seed skills (7 pinned, 2 loadouts, 10 recordings, LLM-judged)
- Content-addressed store with deterministic hashing, prefix lookup, round-trip resolution
- Loadout priority ordering, diff, and multi-agent apply
- LLM judge with blind A/B randomization produces coherent per-task verdicts (8/10 correct attribution on survival run)
- Scout pulls real skills from GitHub (40 found across 4 repos), audits via Haiku, writes safety findings (flagged shell execution, zip-bomb risk, prompt injection — all with specific code citations)
- 24/24 unit tests green (stdlib-only, no pytest dependency)
- Watcher daemon runs persistent on Windows via `pythonw.exe` + PowerShell `Start-Process`

**Not yet proven:**
- Warm-path offer ranking (≥50 recordings). Cold-start is tested; warm needs real accumulated data. V1 of V2 falls back to description fit until the data is there.
- V2 offer pick-logging loop (agent picks one of three → logged → feeds future rankings). The offers are produced; the feedback loop is the next ~30 lines of code.
- Re-engineer pass (scout detects weak tool + external technique → generates upgraded SKILL.md with Sonnet). Pipeline built, gated on weak-tool detection signal accumulating.
- Cross-user data flywheel (cloud sync). Deliberately deferred until local flywheel produces clear value at N=1.

---

## Roadmap

See [roadmap.md](roadmap.md) for full detail.

**V1 — CLI MVP:** ✅ Shipped. Content-addressed store, loadouts, recording, compare, survival test passed.

**V2 — Offer engine:** ✅ Code shipped, cold-start tested. Needs ~1-2 weeks of real watcher runtime to validate warm-path ranking.
- [x] `toolmaster offer <task>` with canonical/iterated/sideways
- [x] BM25F-based cold-start ranking
- [x] Warm-path code path (outcome-weighted) — needs data to validate
- [ ] Pick logging + feedback loop
- [ ] Warm-path empirical validation

**V3 — Background intelligence:** Designed, not built. Three decomposed jobs:
- Dedup: embedding similarity scan, flag duplicate skills
- Scout: GitHub crawler + audit + propose (currently works end-to-end on manual invocation)
- Iterate: fork + mutate + eval against replay logs + surface as offer candidate

---

## Model routing

Different cognitive tasks → different model tiers via OpenRouter or Anthropic direct.

| Task | Model | Cost/call | Why |
|---|---|---|---|
| Scout audit (safety classification) | claude-haiku-4.5 | ~$0.001 | Fast, structured output |
| Loadout compare (blind A/B judge) | claude-haiku-4.5 | ~$0.001 | Structured judgment |
| Skill suggest (relevance ranking) | claude-haiku-4.5 | ~$0.001 | Fast fan-out |
| Re-engineer (rewrite weak tool) | claude-sonnet-4 | ~$0.01 | Creative output |

Overrides: `TOOLMASTER_AUDIT_MODEL`, `TOOLMASTER_COMPARE_MODEL`, `TOOLMASTER_SUGGEST_MODEL`, `TOOLMASTER_REENGINEER_MODEL`, or global `TOOLMASTER_MODEL`.

---

## Security model (for external skill imports)

Three layers before any external skill enters the store:

1. **Static pre-scan** (free, instant): regex patterns for prompt injection, data exfiltration, credential references, obfuscated code, dangerous shell commands. 3+ flags = auto-reject.
2. **LLM audit** (Haiku via OpenRouter): deep analysis of injection vectors, role overrides, safety boundary bypasses, obfuscated payloads. Verdict: `safe` / `caution` / `unsafe`.
3. **Safety gate** (code, free): `unsafe` → rejected; `caution` → extract techniques only (no direct import); `safe` → full import.

Full detail: [ARCHITECTURE.md](ARCHITECTURE.md#security-model)

---

## Who built this, and why

Built by [Haris](https://github.com/techieharry) (Toronto), with Claude Code (Opus 4.6 / 1M context) as the pair-programming co-author. Every commit credits both.

**The problem I had:** 12+ active projects under `C:/Claude/`, 20+ SKILL.md files scattered across them, zero visibility into which ones worked, which combinations worked, or which versions were "last-good" when I edited something and it got worse. Manual skill curation didn't scale past ~5 skills. I wanted a system that would **measure the skill portfolio** the way I measure code quality — per-version, per-composition, per-outcome.

Nothing existing did that, so I built it.

---

## License

TBD. Currently private beta — not yet licensed for redistribution. Ping me if you want access.

---

## Contact

Issues and feedback welcome via GitHub. For the original thinking behind the design decisions and what was killed and why, see [CLAUDE.md](CLAUDE.md).
