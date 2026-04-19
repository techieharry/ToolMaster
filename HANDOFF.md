# ToolMaster Handoff

> Last updated: 2026-04-16 by Claude Opus 4.6 (1M context)
> Status: **Active — V2 shipped · public on GitHub · positioning pivot required after competitive recon**

## Project Summary

ToolMaster is a content-addressed skill registry, LLM-judged eval layer, and autonomous safety-audit pipeline for AI coding agent skills. Originally positioned as a multi-runtime skill registry; **competitive intel gathered 2026-04-16 confirms that lane is now occupied by Anthropic Skills (open standard) + 16+ tools + VoltAgent (17.7k stars) + SkillKit (45 agents) + Skills.sh (Vercel)**. ToolMaster's defensible differentiation is narrower than originally claimed — see "Competitive Intel" section below.

Owner: Haris Yusuf (Toronto). Open-source MIT, public at https://github.com/techieharry/ToolMaster.

V1 thesis proven 2026-04-14 (8/10 LLM-judge attribution). V2 (offer engine + delegate + autopilot) shipped 2026-04-15. Currently positioned as job-portfolio piece while accumulating real flywheel data.

---

## ⚠ Critical: Read Before Building — Competitive Intel (2026-04-16)

**This validates against the previous "Roles" recommendation in HANDOFF and walks it back.**

The previous handoff recommended building a "Roles" feature as Phase 1 of next session — named character classes (Designer, SEO Specialist, etc.) wrapping loadouts. **Web research conducted 2026-04-16 shows this is a saturated market**, not the uncontested category I claimed:

### What's already shipped that overlaps with ToolMaster

| Competitor / Standard | What it ships | When |
|---|---|---|
| **Anthropic Agent Skills** (open standard) | Cross-platform skill format adopted by Claude Code, Cursor, OpenAI Codex, Gemini CLI, GitHub Copilot, JetBrains Junie, OpenHands, Goose, Block, Letta, Mux, Autohand, etc. — 16+ tools native | Dec 2025 |
| **Anthropic Claude Code Subagents** | YAML+markdown agent definitions (name, description, tools, model, system prompt). User-level scope (~/.claude/agents/) for cross-project. Native /eval, /certify, /compare CLI commands | shipped |
| **Anthropic 32-page Skills playbook** | Authoring guide + best practices | Feb 2026 |
| **VoltAgent/awesome-claude-code-subagents** | 130+ subagents in 10 named categories (Core Dev, Language Specialists, Infrastructure, Quality & Security, Data & AI, etc.) | 17.7k stars |
| **VoltAgent/awesome-agent-skills** | 300+ skills cross-platform compatible | 6.9k stars |
| **Skills.sh** (Vercel) | Official directory with telemetry-based leaderboards | shipped |
| **SkillKit** (rohitg00) | Skill package manager that deploys to **45 agents** | shipped |
| **SkillReg** | Private registry for AI agent skills | shipped |
| **CrewAI** | Role/goal/backstory pattern; 100k devs certified, 60% Fortune 500 adoption | mature |
| **IBM Bob** | Built-in agent personas (Ask, Plan, Code, Advanced, Orchestrator) | shipped |

### What ToolMaster claimed vs reality

| Original ToolMaster claim | Reality 2026 |
|---|---|
| Content-addressed SHA-256 skill versioning | **Probably still unique** — most registries are mutable. Worth keeping. |
| Loadouts as composition unit | Not unique — Subagents and CrewAI Crews are compositional |
| **Loadout-vs-loadout LLM eval** | Anthropic ships `/eval`, `/certify`, `/compare`. Skills.sh has telemetry rankings. **Need to differentiate on methodology, not existence.** |
| Autonomous scout + audit + propose | **Probably still unique** — most registries are human-curated trust-based. **This is the real edge.** |
| Cross-project data flywheel | User-level Subagents already cross-project natively |
| Skill dispatch (delegate primitive) | Subagents ARE the dispatch primitive in Claude Code natively |
| Multi-agent targets (7 IDEs) | SkillKit deploys to 45. Anthropic Skills works on 16+. **This story is dead.** |
| **"Named roles with spec sheets" (was: Phase 1 next session)** | **VoltAgent has 130+ in 10 categories. This is what they sell.** |

### What remains genuinely differentiated

Three things, narrower than originally sold:

1. **Autonomous safety audit pipeline** ([scout.py](toolmaster/scout.py)) — runs LLM safety audits on external skills BEFORE import. Surfaces specific findings like "shell injection via unsanitized project-name" or "Facebook Ad Library scraping violates ToS". I haven't found anyone else running this. Community registries are trust-based — they distribute, they don't audit. **This is real.**
2. **Blind A/B LLM judge methodology with position randomization** ([compare.py](toolmaster/compare.py)) — the V1 survival test (8/10 attribution) is publishable as a research methodology post. Anthropic's `/compare` exists but the methodology specifics (blind A/B, randomization to eliminate position bias) may differ.
3. **Per-user task-outcome data flywheel** — edit distance, ratings, rejection rates per skill per project per loadout. Anthropic has telemetry but doesn't see per-task outcomes by definition (they don't sit between user and code). This is hard to replicate but only matters at scale.

### The positioning pivot

**Old**: "ToolMaster is a content-addressed skill registry with loadout eval for AI coding agents." → competes against Anthropic Skills + VoltAgent + Skills.sh + SkillKit head-on.

**New**: "ToolMaster is the autonomous safety audit + outcome eval layer that sits on top of any skill source — Anthropic Skills, VoltAgent, custom Subagents, GitHub repos." → operates one layer above the supply, doesn't compete on supply itself.

This pivot requires updating: README.md headline, CLAUDE.md positioning, ARCHITECTURE.md framing, the GitHub repo description. NOT the underlying code — the code is fine, the framing was wrong.

---

## Session Log

### 2026-04-16 — Competitive recon, positioning pivot, handoff rewrite
- **Web research validated against the Roles recommendation.** Found 16+ tools natively shipping Anthropic Skills, multiple registries (VoltAgent 17.7k+6.9k, Skills.sh, SkillReg, SkillKit), Anthropic Subagents native primitive, Anthropic /eval /certify /compare CLI. The "Roles as named class system" lane I recommended building is fully occupied.
- **Positioning pivot identified**: stop competing on supply (skill registry / role library), reposition as the audit + eval layer ON TOP of existing supply. Three defensible edges: autonomous safety audit, blind A/B judge methodology, per-user outcome flywheel.
- **Walked back the Roles recommendation in this handoff.** Next session should NOT build Roles. See "Next Steps" for the corrected priorities.
- **Visualizations + RPG TUI shipped** earlier in session: `toolmaster live` (5-tab dashboard server), `toolmaster viz` (single HTML), `toolmaster armory` (RPG terminal — personal use only, terminal emoji rendering varies).
- **Public GitHub launch**: techieharry/ToolMaster public, MIT license, polished README. Profile repo techieharry/techieharry created. Display name "Haris Yusuf", bio, location set via classic PAT (revoked after).

### 2026-04-15 — V2 ships + autonomous loop + scout expansion
- **V2 offer engine** (`toolmaster offer <task>`): canonical / iterated / sideways ranking with cold-start BM25F + warm-path outcome weighting (≥50 recordings threshold, default min_relevance 0.05).
- **Delegate primitive** (`toolmaster delegate "..." --loadout X -y`): dispatches a specialist Haiku/Sonnet agent with the loadout's skills loaded as system prompt. Captures output, writes recording. Smoke-tested: produced refactored code citing "pyramid of doom" vocabulary from skill body — proves loadout payload actually shapes specialist reasoning.
- **Autopilot** (`toolmaster autopilot "..."`): one-shot offer + delegate with safe fallback when no loadout clears relevance threshold.
- **Multi-agent targets**: 7 IDEs supported via `loadout apply --target {claude,agents,cursor,codex,aider,windsurf,continue}`. (Note: SkillKit covers 45 — this story is no longer differentiating.)
- **Cost preview + cache** in `compare`: estimates token count + USD before LLM judge runs; results cached by `(loadout-pair, recording-set)` SHA-256 hash.
- **Scout discovery expanded ~9×**: 5 → 19 hardcoded watched repos, GitHub Topics rotation (8 topics), awesome-list mining (6 lists). Auth via `_github_headers()` (60→5000 req/hr).
- **Real production data harvested**: sync pulled 11 real skills from `myagency` + `Virtual_Controller` projects. Watcher daemon ran 380+ cycles, 442 external skills LLM-audited via Haiku, 27 proposals written.
- **Bugs fixed**: `sync.py` stale `CLAUDE_DIR`, scout cp1252 encoding crash, scout's `_distribute_proposals` stale path, watcher pythonw stdout buffering (`-u` flag), cp1252 sweep across 19 `read_text()` call sites in 10 modules, missing CSS classes in live dashboard, drag-vs-zoom event conflict in graph.

### 2026-04-14 — Reconciliation + V1 survival test — **THESIS PROVEN**
- Code was well ahead of `roadmap.md`; reconciled in place.
- `tests/test_v1_survival.py` created (13 tests, all green).
- **Survival test: 8/10 correct attribution.** 5/5 bug-fix tasks → bugfix_stack, 3/5 refactor tasks → refactor_stack. Per-task LLM reasoning was specific and coherent. Per `CLAUDE.md:88-90`, V1 condition met. V2 unlocked.
- Renamed Forge → ToolMaster everywhere (Forge was too common a name).

(Append new sessions above this line, keep last 5 max. Archive to HANDOFF_ARCHIVE.md if needed.)

---

## Current State

### What Works (validated end-to-end with real data, 46/46 tests green)
- **Content-addressed store** (`store.py`): SHA-256 manifests, pin/resolve/ls/show, prefix-hash lookup, hash stability.
- **Quality gate** (`quality.py`): 0–100 score, critical-issue auto-fail, security pattern pre-scan.
- **Loadouts** (`loadout.py`): create/show/list/apply/diff with `toolmaster.lock` sidecar. 7 agent targets.
- **Recordings** (`record.py`): quick_record, list, filter, rate.
- **Compare** (`compare.py`): blind A/B LLM judge via OpenRouter or Anthropic. Heuristic fallback. Cost estimate + result caching.
- **V2 Offer engine** (`offer.py`): BM25F-based cold-start + warm-path outcome weighting. Returns canonical / iterated / sideways.
- **V2 Delegate primitive** (`delegate.py`): dispatches specialist agent with pinned loadout. Recording auto-written.
- **V2 Autopilot**: offer + delegate in one verb.
- **Suggest engine** (`suggest.py`): individual skill ranking via 7-signal BM25F (`matcher.py`).
- **Protocol** (`protocol.py` v1.1): checkin returns toolbox state + loadouts; checkout returns both skill suggestions and loadout offers.
- **Scout** (`scout.py`): GitHub crawler with 3-tier discovery (19 repos + 8 topics + 6 awesome lists), static security pre-scan + LLM audit via Haiku, proposal writer, re-engineering pipeline. **442 external skills audited, 27 proposals written. This is the differentiated layer.**
- **Sync** (`sync.py`): cross-project skill harvest, agent prompt distribution, CLAUDE.md enforcement injection. 11 real skills harvested.
- **Global watcher daemon** (`global_watcher.py`): poll/sync/scout scheduler. May or may not be currently running — verify with `tasklist | grep pythonw`.
- **Static viz** (`viz.py`): single-HTML D3 force-directed graph.
- **Live dashboard** (`live.py`): stdlib HTTP server on `:8484`, 5 polling tabs (Overview / Graph / Research / Proposals / Skills), mobile responsive, drag-vs-zoom fix.
- **Armory TUI** (`armory.py`): personal-use only — terminal emoji rendering varies.

### What's Broken / Blocked / At-Risk
- **Positioning is misaligned with reality.** README + CLAUDE.md + ARCHITECTURE pitch ToolMaster against now-shipped competitors. Top priority next session.
- **No PyPI release yet.** `pyproject.toml` ready with `name = "toolmaster"`. Confirm name available on PyPI. Hold publish until positioning pivot is in.
- **Warm-path V2 ranking unvalidated.** 7 recordings total; need 50+ before warm path engages.
- **Watcher daemon may not be running.** `tasklist | grep pythonw` to check.
- **Pin ToolMaster on profile**: web UI only — https://github.com/techieharry → "Customize your pins".
- **Re-engineer pipeline failing on `social-posts`** with cp1252 encoding errors. Low priority.

### What's Partially Done
- **Pick logging for V2 autopilot**: when an agent runs `toolmaster offer` and chooses one, the choice isn't logged back. ~30 lines, deferred.
- **Anthropic Skills marketplace ingest**: discussed but not built. Now critical to the new positioning — see Next Steps.
- **Multi-agent targets story**: deprecated as a marketing claim (SkillKit beats us at 45 vs our 7). Code stays; messaging changes.

---

## Next Steps (Priority Order — REVISED 2026-04-16 after competitive recon)

### 1. **Positioning pivot — update README + CLAUDE.md + ARCHITECTURE + repo description**

This is the highest-leverage move. The code is fine; the framing was wrong. Specifically:

**README.md changes:**
- Old headline: "Content-addressed skill registry + LLM-judged loadout evaluation"
- New headline: "**Autonomous safety audit + LLM-judged outcome eval for AI coding agent skills**"
- Add a "How this complements Anthropic Skills" section — explicitly position ToolMaster as the layer ABOVE the standard, not a competitor to it
- Emphasize: scout's safety audit (specific findings citation), blind A/B judge methodology, per-user outcome flywheel
- De-emphasize: skill registry features, multi-agent target count, individual loadout management
- Update comparison table — remove rows where Anthropic/VoltAgent/SkillKit now match us

**CLAUDE.md changes:**
- Update "What ToolMaster IS NOT" section: add "Not a competitor to Anthropic Agent Skills — it's the audit + eval layer that sits on top."
- Update "Survival condition" to reflect new positioning thesis

**GitHub repo description** (set via `gh repo edit`):
- Old: "Content-addressed skill registry + loadout system + LLM-judged evaluation for AI coding agents..."
- New: "Autonomous safety audit + blind A/B LLM-judged outcome evaluation for AI agent skills. Audits external skills before import (scout); ranks loadouts by historical task outcomes (compare). Sits on top of Anthropic Agent Skills."

**Estimated time**: 1-2 hours of focused writing + 1 commit.

### 2. **Build the registry ingestion bridge — `scout.py` ingests from Skills.sh + VoltAgent + Subagents**

Currently `scout.py` only crawls GitHub repos. Adding ingestion from existing registries makes ToolMaster the safety audit + outcome eval layer for the WHOLE ecosystem instead of competing on supply.

Concrete additions to `scout.py`:
- `_fetch_skills_sh()` — pulls skills from Skills.sh API/leaderboard. Treats them as Tier-1 candidates.
- `_fetch_voltagent_subagents()` — clones VoltAgent/awesome-claude-code-subagents, parses YAML+markdown subagents, treats each as a candidate skill.
- `_fetch_anthropic_subagents()` — scans `~/.claude/agents/` for user-level subagents and adds them as candidates for audit + eval.
- Each goes through the existing security audit pipeline. Each gets a recording when used.

**Why this is differentiated**: nobody else audits skills from these registries. ToolMaster becomes the "did anyone check this is safe?" service for the entire ecosystem.

**Estimated time**: 3-4 hours. Reuses all existing scout infrastructure.

### 3. **Write the survival test as a publishable methodology post**

Title draft: **"Can an LLM judge pick the right stack of skills for a coding task? A blind A/B survival test with position randomization (n=10)."**

This is the academic-rigor portfolio piece. The methodology (blind A/B with position randomization) is the differentiation, not just the result.

Structure:
- Setup (two differentiated loadouts, 10 recorded tasks)
- Methodology (blind A/B, position randomization, why those matter for LLM judges)
- Results (8/10 attribution, per-task reasoning analysis)
- Discussion (what this means for skill composition eval generally)
- Reproduction instructions (link to `tests/run_v1_survival.py`)

Publish on Medium, GitHub Pages, or personal site. Cross-post to /r/MachineLearning, /r/LocalLLaMA, HN.

**Estimated time**: 2-3 hours of focused writing.

### 4. **Verify / restart the watcher daemon**
- `tasklist | grep pythonw` — if no process, daemon is dead.
- Restart: `bash hooks/run-watcher.sh start` or `powershell -File hooks/run-watcher.ps1 start`. `.env` is populated.
- Confirm with `python -m toolmaster watch --status`.

### 5. **Expand recordings corpus to ≥50 for warm-path V2 validation**
- Use ToolMaster on real agent work: `toolmaster record -t "..." -o "..." -l <loadout> -r 4`.
- OR rely on watcher harvest from project log files.
- Currently at 7. Target 50+.

### 6. **Hacker News "Show HN" — but only AFTER positioning pivot lands**
- Title (revised): "Show HN: ToolMaster — autonomous safety audit + blind A/B LLM judge for AI agent skills"
- Hook: V1 survival test (8/10), real security findings from scout audits (the Facebook ad scraper rejection, MCP supply-chain CAUTIONs)
- Best window: Tuesday/Wednesday morning Eastern
- Don't launch until positioning is corrected — launching with the old framing will get critiqued in comments

### 7. **Pin ToolMaster on the GitHub profile** (manual web UI only)

### ~~Build "Roles" feature (named character classes)~~ — **DROPPED 2026-04-16**

This was the previous handoff's #1 priority. Walked back after competitive recon. VoltAgent/awesome-claude-code-subagents (17.7k stars) + Anthropic Subagents native + 130+ existing role-shaped subagents = the lane is occupied. Building this would be a 4th-place entry. Don't do it.

If a role-like UX layer is ever wanted, **adopt the Anthropic Subagent format directly** so ToolMaster's loadouts ARE Subagents. Don't invent a competing role spec.

---

## Key Decisions (Do Not Revisit)

| Decision | Why | Date |
|---|---|---|
| Kill five-slot grammar | Fights ecosystem markdown standard | 2026-04-11 |
| Kill composition operators | Skills are behavioral layers, not typed functions | 2026-04-11 |
| Loadout is the unit of composition | Thesis question is "does this stack beat that stack?" | 2026-04-11 |
| Python + stdlib-only for V1 core | Fast prototype, easy PyPI | 2026-04-11 |
| Blind A/B randomization in compare | Eliminates position bias in LLM judge | 2026-04-14 |
| Rename Forge → ToolMaster everywhere | "Forge" too common | 2026-04-14 |
| Delegate is one-call primitive, NOT orchestration | CrewAI/AutoGen own that lane | 2026-04-15 |
| Default min_relevance for autopilot = 0.05 | Empirically tuned against BM25F cold-start | 2026-04-15 |
| Live dashboard uses stdlib `http.server` | Zero-dep promise; D3 from CDN is the only external | 2026-04-16 |
| RPG TUI is personal-use only | Terminal emoji rendering inconsistent | 2026-04-16 |
| **Drop "skill registry" positioning, pivot to "safety audit + outcome eval layer"** | Anthropic Skills + VoltAgent + SkillKit + Skills.sh occupy the registry lane | **2026-04-16** |
| **Drop Roles concept** | VoltAgent (17.7k stars) + Subagents native already serve this | **2026-04-16** |
| **Reframe `scout.py` as the headline feature** | Autonomous safety audit is the genuinely unique edge | **2026-04-16** |

---

## Architecture / File Map

```
C:\Claude\ToolMaster\                  github.com/techieharry/ToolMaster (PUBLIC, MIT)
├── README.md                          ⚠ Needs positioning rewrite (Next Step #1)
├── LICENSE                            MIT
├── CLAUDE.md                          ⚠ Needs positioning rewrite (Next Step #1)
├── ARCHITECTURE.md                    ⚠ Needs positioning rewrite (Next Step #1)
├── HANDOFF.md                         ← this file
├── TOOLMASTER_AGENT_PROMPT.md         V2 decision tree (auto-distributed by sync)
├── roadmap.md                         Reconciled with code reality
├── pyproject.toml                     `name = "toolmaster"`, console_script wired
├── .env                               OPENROUTER_API_KEY + GITHUB_TOKEN (GITIGNORED)
├── .env.example                       Template
├── .gitignore                         Excludes .env, runtime state, viz output
├── toolmaster/                        Python package, 20 modules, stdlib only
│   ├── store.py                       Content-addressed SHA-256 store
│   ├── loadout.py                     7 agent targets (claude/cursor/codex/...)
│   ├── record.py                      Task recordings
│   ├── compare.py                     Blind A/B LLM judge + cost preview + cache
│   ├── offer.py                       V2 offer engine (canonical/iterated/sideways)
│   ├── delegate.py                    Skill dispatch primitive + autopilot
│   ├── suggest.py                     BM25F skill ranking
│   ├── matcher.py                     7-signal BM25F (exact/prefix/phrase/fuzzy)
│   ├── quality.py                     Skill quality gate (0-100)
│   ├── protocol.py                    Agent session protocol v1.1
│   ├── scout.py                       ⭐ Headline differentiator — GitHub crawl + LLM audit + propose
│   ├── sync.py                        Cross-project harvest + push
│   ├── global_watcher.py              Background daemon
│   ├── trust.py                       External repo trust filter
│   ├── viz.py                         Static D3 HTML generator
│   ├── live.py                        Multi-tab live dashboard server
│   ├── armory.py                      RPG TUI (personal use only)
│   └── cli.py                         CLI entry — 21 commands
├── tests/
│   ├── test_v1_survival.py            46 stdlib-only tests, all green
│   └── run_v1_survival.py             End-to-end survival driver (LLM judge)
├── hooks/
│   ├── run-watcher.ps1                Windows daemon launcher (pythonw, -u, .env-aware)
│   ├── run-watcher.sh                 Unix daemon launcher
│   ├── session-start.sh               Notification hook (auto-checkin)
│   ├── session-end.sh                 Stop hook (auto-return)
│   ├── pre-write-check.sh             PreToolUse hook (SKILL.md guard)
│   └── auto-log.sh                    Legacy stop hook
├── skills/                            7 seed skills
└── docs/
    ├── v1-survival-results.md         Full survival test output
    ├── discovery-sources.md           3-tier scout discovery catalog
    ├── competitive-analysis.md        ⚠ Outdated — needs 2026-04-16 update
    ├── immutable-parts.md
    ├── roguelike-selection.md
    └── toolbox-master.md
```

Profile repo: `C:\Claude\techieharry-profile\` → github.com/techieharry/techieharry (PUBLIC)

---

## State / Config

| Item | Location | Notes |
|---|---|---|
| Global store | `~/.toolmaster/store/` | 11 pinned skills |
| Recordings | `~/.toolmaster/recordings/` | 7 (need 50+ for V2 warm path) |
| Loadouts | `~/.toolmaster/loadouts/` | empty in real store; tests use tmp dirs |
| Proposals | `~/.toolmaster/proposals/` | 27 scout proposals |
| Scout state | `~/.toolmaster/scout_state.json` | 51 cycles, 442 audited, 371 known repos |
| Watcher state | `~/.toolmaster/global_watcher_state.json` | per-project log tracking |
| Insights | `~/.toolmaster/global_insights.json` | per-project + per-skill metrics |
| Watcher PID | `~/.toolmaster/watcher.pid` | last-known PID; verify process alive |
| Logs | `~/.toolmaster/{watcher,scout}.log` | UTF-8 encoded |
| Compare cache | `~/.toolmaster/compare_cache/` | LLM judge results cached by hash |
| API keys | `C:\Claude\ToolMaster\.env` | OPENROUTER_API_KEY, GITHUB_TOKEN, CLAUDE_DIR (GITIGNORED) |
| Dashboard port | `localhost:8484` | `toolmaster live --port 8484` |

---

## Dependencies / External Systems

- **Python 3.14** — confirmed working; pure stdlib core
- **OpenRouter** (preferred) or **Anthropic API** for LLM calls (audit, compare, delegate, suggest, re-engineer)
- **GitHub API** (5000 req/hr authed via `GITHUB_TOKEN` from `.env`)
- **No cloud services** — entirely local, all state in `~/.toolmaster/`
- **`gh` CLI** for GitHub auth and ad-hoc API calls

---

## Known Issues / Gotchas

- **`gh` CLI uses `GH_TOKEN` env (set by `gh auth login`) before `GITHUB_TOKEN`.** When overriding tokens for one-off commands, use `GH_TOKEN=...` not `GITHUB_TOKEN=...`. (Cost 30 minutes earlier this session.)
- **GitHub fine-grained PATs vs classic PATs**: fine-grained PATs (prefix `github_pat_11...`) cannot create repos, change visibility, or update user profile. Classic PATs (prefix `ghp_`) with `repo` + `user` scopes can. Default from `gh auth login` is fine-grained.
- **Pinning repos on a profile has no public API.** Manual web UI only.
- **Quality gate rejects external skills with critical issues.** Most external skills from GitHub fail the gate; scout's audit + extract_techniques flow handles this.
- **`compare_loadouts` silently falls back to heuristic with no API key.** CLI prints `Method: heuristic` — confirm before trusting results.
- **`toolmaster.lock` is written to `target_dir.parent`**, not `target_dir`. Correct per code, but worth remembering.
- **Live dashboard graph drag**: only works after `e.sourceEvent.stopPropagation()` fix (already in). Without it, dragging a node also pans.
- **`pythonw` on Windows buffers stdout aggressively.** Use `-u` flag in any new launcher (already in `hooks/run-watcher.ps1`).
- **Many `.read_text()` calls swept to `encoding="utf-8", errors="replace"` 2026-04-15.** Follow the pattern for new file reads.
- **CLAUDE_DIR is hardcoded historically in 3 places** (global_watcher, scout, sync). All now read from env with `C:/Claude` default.
- **The 11 pinned skills include weak ones like `social-posts` (83% edit, 1 rejection).** Re-engineering keeps trying and failing on cp1252. Safe to ignore.

---

## Quick-Start for Next Session

```bash
# 1. Verify watcher state
tasklist | grep pythonw                       # Windows
python -m toolmaster watch --status           # works regardless

# 2. If watcher is dead, restart
bash hooks/run-watcher.sh start               # or powershell hooks/run-watcher.ps1 start

# 3. Open the live dashboard for context
python -m toolmaster live                     # http://localhost:8484

# 4. Run tests to confirm clean baseline
python -m unittest tests.test_v1_survival     # should be 46/46 green

# 5. Pull latest if working on different machine
git pull origin main

# 6. Read top 3 priorities in this file's "Next Steps" section
#    (Hint: Next Step #1 is the positioning rewrite — README/CLAUDE.md/ARCHITECTURE)
```

**Critical**: read the "Competitive Intel (2026-04-16)" section near the top of this file BEFORE starting any new feature work. The Roles concept that was previously the recommended next direction has been dropped. The new direction is positioning pivot + scout-as-headline + registry ingestion bridge.

---

*This handoff follows the standard template from `C:\Claude\handoff-engine\HANDOFF_TEMPLATE.md`. Updated by the agent at session end on 2026-04-16 after web validation of competitive landscape.*
