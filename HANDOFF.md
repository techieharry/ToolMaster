# ToolMaster Handoff

> Last updated: 2026-04-16 by Claude Opus 4.6 (1M context)
> Status: **Active — V2 shipped end-to-end · public on GitHub · roles concept queued as next strategic direction**

## Project Summary

ToolMaster is a content-addressed skill registry, loadout system, LLM-judged eval layer, and skill-dispatch primitive for AI coding agents. Targets Claude/Cursor/Codex/Aider/Windsurf/Continue. Owned by Haris Yusuf (Toronto), open-source MIT, public at https://github.com/techieharry/ToolMaster. **V1 thesis proven 2026-04-14 (8/10 LLM-judge attribution); V2 (offer engine + delegate primitive + autopilot) shipped 2026-04-15.** Currently positioned as job-portfolio piece while accumulating real flywheel data.

---

## Session Log

### 2026-04-16 — Visualizations + Public Launch + Roles Direction
- **Live dashboard** (`toolmaster live`): zero-dep stdlib HTTP server with 5 polling tabs (Overview / Graph / Research / Proposals / Skills). Mobile-responsive (3 breakpoints). D3 force-directed graph with hover-highlight, drag-vs-zoom event fix.
- **Static viz** (`toolmaster viz`): single-HTML interactive D3 graph with 18-char name truncation, text-shadow halos, zoom-to-fit, neighbor highlighting.
- **RPG TUI** (`toolmaster armory`): pure ANSI + Unicode + emoji terminal inventory with rarity tiers (Legendary/Epic/Rare/Uncommon/Broken), star ratings, lore-formatted scout logs. Honest caveat: terminal emoji rendering is inconsistent across fonts; web theme is the better RPG canvas.
- **Public GitHub launch**: `techieharry/ToolMaster` flipped public, MIT LICENSE, polished portfolio README with V1 survival result + comparison table + 60-second demo. Profile repo `techieharry/techieharry` created with featured project card. Display name + bio + location set via classic PAT (revoked after).
- **Topics added**: `ai-agents`, `claude-code`, `llm-evaluation`, `skill-registry`, `python`, `content-addressable-storage`, `agent-framework`, `developer-tools`.
- **Strategic concept queued**: "Roles" — reframe loadouts as named character classes (Designer / SEO Specialist / Strategist / Refactorer / Bug Hunter) with spec sheets, promotion paths, and class hierarchies. See `Next Steps` for details. **This is the highest-leverage product direction identified so far.**
- 46/46 tests green. 18 commits this session.

### 2026-04-15 — V2 ships + autonomous loop + scout expansion
- **V2 offer engine** (`toolmaster offer <task>`): canonical / iterated / sideways ranking with cold-start BM25F + warm-path outcome weighting (≥50 recordings threshold, default min_relevance 0.05).
- **Delegate primitive** (`toolmaster delegate "..." --loadout X -y`): dispatches a specialist Haiku/Sonnet agent with the loadout's skills loaded as system prompt. Captures output, writes recording. Smoke-tested: produced refactored code citing "pyramid of doom" vocabulary from skill body — proves loadout payload actually shapes specialist reasoning.
- **Autopilot** (`toolmaster autopilot "..."`): one-shot offer + delegate. Falls back safely when no loadout clears relevance threshold.
- **Multi-agent targets**: 7 IDEs supported via `loadout apply --target {claude,agents,cursor,codex,aider,windsurf,continue}`.
- **Cost preview + cache** in `compare`: estimates token count + USD before LLM judge runs; results cached by `(loadout-pair, recording-set)` SHA-256 hash.
- **Scout discovery expanded ~9×**: 5 → 19 hardcoded watched repos, GitHub Topics rotation (8 topics), awesome-list mining (6 lists). Auth via `_github_headers()` (60→5000 req/hr).
- **Real production data harvested**: sync pulled 11 real skills from `myagency` + `Virtual_Controller` projects (marketing-copy, social-posts, strategy-doc, quotation, deploy, security-review, etc.). Watcher daemon ran 380+ cycles, 442 external skills LLM-audited via Haiku, 27 proposals written.
- **Bugs fixed**: `sync.py` stale `CLAUDE_DIR`, scout cp1252 encoding crash, scout's `_distribute_proposals` stale path, watcher pythonw stdout buffering (`-u` flag in PowerShell launcher), cp1252 sweep across 19 `read_text()` call sites in 10 modules, missing CSS classes in live dashboard, drag-vs-zoom event conflict in graph.
- `TOOLMASTER_AGENT_PROMPT.md` rewritten with V2 decision tree; sync layer pushes to all 12 projects under `C:/Claude/`.

### 2026-04-14 — Reconciliation + V1 survival test — **THESIS PROVEN**
- Code was well ahead of `roadmap.md` — V1 Steps 1–4 implemented but unchecked. Reconciled in place.
- `tests/` was empty; created `test_v1_survival.py` (13 tests, all green).
- **Survival test result: 8/10 correct attribution.** 5/5 bug-fix tasks → bugfix_stack, 3/5 refactor tasks → refactor_stack (1 tie, 1 disputable). Per-task LLM reasoning was specific and coherent. Per `CLAUDE.md:88-90`, V1 condition met. V2 unlocked.
- Renamed Forge → ToolMaster everywhere (Forge was too common a name).

(Append new sessions above this line, keep last 5 max. Archive to HANDOFF_ARCHIVE.md if needed.)

---

## Current State

### What Works (validated end-to-end with real data)
- **Content-addressed store** (`store.py`): SHA-256 manifests, pin/resolve/ls/show, prefix-hash lookup, hash stability across re-pins, deterministic blob storage.
- **Quality gate** (`quality.py`): 0–100 score, critical-issue auto-fail, security pattern pre-scan. Threshold 60 normal / 80 strict.
- **Loadouts** (`loadout.py`): create/show/list/apply/diff with `toolmaster.lock` sidecar. 7 agent targets via `AGENT_TARGETS` dict.
- **Recordings** (`record.py`): `quick_record`, list, filter by loadout, rate (1-5).
- **Compare** (`compare.py`): blind A/B LLM judge via OpenRouter (Haiku 4.5 default) or Anthropic direct. Heuristic fallback. Cost estimate + result caching by `(loadout-pair-hash, recording-set-hash)`.
- **V2 Offer engine** (`offer.py`): BM25F-based cold-start ranking + warm-path outcome weighting. Returns canonical / iterated / sideways. Validated: refactor tasks pick refactor_stack, bug tasks pick bugfix_stack.
- **V2 Delegate primitive** (`delegate.py`): dispatches specialist agent with pinned loadout. Cost preview, dry-run, confirmation gate. Recording auto-written.
- **V2 Autopilot**: offer + delegate in one verb.
- **Suggest engine** (`suggest.py`): individual skill ranking via BM25F + 7-signal matcher (`matcher.py`).
- **Protocol** (`protocol.py` v1.1): checkin returns toolbox state + loadouts; checkout returns both skill suggestions and loadout offers.
- **Scout** (`scout.py`): GitHub crawler with 3-tier discovery (19 repos + 8 topics + 6 awesome lists), static security pre-scan + LLM audit via Haiku, proposal writer, re-engineering pipeline. 442 external skills audited as of last session.
- **Sync** (`sync.py`): cross-project skill harvest, `TOOLMASTER_AGENT_PROMPT.md` distribution, `CLAUDE.md` enforcement block injection. 11 real skills harvested + 12 projects synced this session.
- **Global watcher daemon** (`global_watcher.py`): poll/sync/scout scheduler. Launched via `hooks/run-watcher.ps1` (Windows pythonw, detached). Was running PID 12000 mid-session; **likely killed when terminal sessions ended — verify with `tasklist | grep pythonw`**.
- **Static viz** (`viz.py`): single-HTML D3 force-directed graph with sidebar stats + scout proposals.
- **Live dashboard** (`live.py`): stdlib HTTP server on `:8484`, 5 polling tabs (Overview / Graph / Research / Proposals / Skills), mobile responsive at 3 breakpoints, D3 graph with hover-highlight + drag fix.
- **Armory TUI** (`armory.py`): pure ANSI + Unicode + emoji RPG inventory in terminal. Honest caveat — terminal emoji rendering varies; consider this a personal-use tool, not portfolio-facing.
- **46/46 tests green** (`tests/test_v1_survival.py`): store, loadout, record, compare, offer, delegate, autopilot, multi-agent targets, scout discovery config, viz HTML structure, protocol V2.

### What's Broken / Blocked
- **No PyPI release yet.** `pyproject.toml` ready with `name = "toolmaster"`. Need to: confirm PyPI name available, write changelog, `python -m build && twine upload`. Blocking nothing critical.
- **Warm-path V2 ranking unvalidated.** Cold-start works (BM25F) but the warm path (outcome-weighted) needs ≥50 recordings per loadout to engage. Current state: 7 recordings total. Need 1-2 weeks of real watcher runtime to accumulate.
- **Watcher daemon may not be running.** Last verified PID 12000 mid-session but terminal teardown may have killed it. Check with `tasklist | grep pythonw`. If dead, restart via `bash hooks/run-watcher.sh start` or `powershell -File hooks/run-watcher.ps1 start`.
- **Pin ToolMaster on profile**: must be done via web UI at https://github.com/techieharry — no public API for pinned items even with full PAT scope.
- **Armory TUI rendering quality varies by terminal**. Emoji width is inconsistent across monospace fonts; column alignment may break. Use the live dashboard for portfolio demos instead.

### What's Partially Done
- **Re-engineer pipeline**: code exists in `scout.py` but `social-posts` re-engineering attempts have been failing on cp1252 encoding errors. Last verified in scout.log around 2026-04-15. Probably needs another encoding fix in the re-engineer code path.
- **Pick logging for V2 autopilot**: when an agent runs `toolmaster offer` and chooses one, the choice isn't logged back to feed future rankings. ~30 lines of code; deferred until offer engine has real usage data.
- **Anthropic marketplace ingest**: discussed as a scout source but not implemented. Would parallel `_fetch_repos_by_topic()` — pull from Claude Desktop extensions list and treat as Tier-1 candidates.

---

## Next Steps (Priority Order)

### 1. **Roles** (next strategic direction — biggest leverage)

**The idea**: Reframe loadouts as named **character classes** (Designer / SEO Specialist / Strategist / Refactorer / Bug Hunter / Reviewer / Documenter / etc.) with spec sheets, promotion paths, and class hierarchies. Loadouts become an implementation detail; roles are the user-facing primitive.

**Why it matters**:
- Moves ToolMaster out of the crowded "skill registry" lane (where Anthropic Skills, wshobson/agents, ComposioHQ all compete) into a category nobody owns: **the class system for AI agents**.
- Makes `offer` results legible: "Junior Designer / Brand Designer / UX Strategist" beats "loadout_a / loadout_b / loadout_c" on every dimension.
- Makes V1 survival result more publishable: "Senior Refactorer beat Senior Debugger 8/10 on refactor tasks" reads like a real benchmark.
- Natural fit for the gamified RPG aesthetic — class card IS the natural display for a role.
- The progression mechanic (Junior → Senior → Lead) maps to model tier escalation (Haiku → Sonnet → Opus) and skill breadth.

**Phase 1 build (≈300-500 lines, 1 focused session)**:
- `toolmaster/roles.py`: Role class wrapping a loadout + metadata (name, description, level, parent_role, archetype, when_to_use, when_not_to_use, skill_hashes).
- 10-15 seed roles in `roles/` directory: `designer.md`, `seo-specialist.md`, `strategist.md`, `marketer.md`, `refactor-engineer.md`, `bug-hunter.md`, `test-author.md`, `code-reviewer.md`, `documenter.md`, etc.
- CLI: `toolmaster role list` / `role show <name>` / `role equip <name> --target claude`.
- Role registry as content-addressed (same SHA-256 system, just at the role level — roles point to skill hashes).
- Each role's spec sheet rendered as a "class card" in the web dashboard.

**Phase 2** (next session after Phase 1):
- Promotion paths
- Multi-role composition ("Designer + SEO" = "Brand Designer")
- Scout proposes role extensions, not just skills
- `toolmaster.lock` records equipped role per project
- Migration: existing loadouts get a `role:` field (refactor_stack → "Refactor Engineer", bugfix_stack → "Bug Hunter")

**Recommended approach**: open a fresh session, point at the design spec in this section, build Phase 1 in a focused 2-3 hour push. Don't start without committing to the design — the role-naming taxonomy is the load-bearing decision.

### 2. **Verify / restart the watcher daemon**
- `tasklist | grep pythonw` — if no process, daemon is dead.
- If dead: `OPENROUTER_API_KEY=... GITHUB_TOKEN=$(gh auth token) bash hooks/run-watcher.sh start` OR rely on `.env` (already populated, gitignored).
- Confirm with `python -m toolmaster watch --status`.

### 3. **Expand recordings corpus to ≥50 for warm-path V2 validation**
- Use ToolMaster on real agent work: `toolmaster record -t "..." -o "..." -l <loadout> -r 4`
- OR rely on watcher harvest from project log files (already operating)
- Target: 50+ recordings before trusting warm-path ranking. Currently at 7.

### 4. **Hacker News "Show HN" launch**
- Repo is public, README is ready, MIT licensed.
- Title: "Show HN: ToolMaster — content-addressed skill registry with LLM-judged loadout evaluation for AI coding agents"
- Hook: the V1 survival test result (8/10 attribution).
- Best window: Tuesday/Wednesday morning Eastern.
- Don't launch until you're ready to engage in comments for ~6 hours.

### 5. **Pin ToolMaster on the GitHub profile**
- Manual web UI: https://github.com/techieharry → "Customize your pins" → check ToolMaster.
- No API for this even with full PAT.

### 6. **Smaller residuals**
- Pick logging for V2 autopilot (~30 lines)
- Anthropic marketplace as scout source (parallel to existing topic/awesome ingest)
- PyPI publish (after roles, so the package ships with the new primitive)
- Re-engineer cp1252 fix (low priority — re-engineer rarely fires)
- Tests for protocol/scout/sync (only V1 thesis path is tested currently)

---

## Key Decisions (Do Not Revisit)

| Decision | Why | Date |
|---|---|---|
| Kill five-slot grammar | Fights ecosystem markdown standard | 2026-04-11 |
| Kill composition operators | Skills are behavioral layers, not typed functions | 2026-04-11 |
| Decompose toolbox master into poll/sync/scout/protocol | Monolith was three systems wearing a trenchcoat | 2026-04-11 |
| Loadout is the unit of composition (not individual skills) | The thesis question is "does this stack beat that stack?" | 2026-04-11 |
| Python + stdlib-only for V1 core | Fast prototype, Haris's stack, easy PyPI | 2026-04-11 |
| Blind A/B randomization in compare | Eliminates position bias in LLM judge | 2026-04-14 |
| Rename Forge → ToolMaster everywhere | "Forge" is too common a name | 2026-04-14 |
| Delegate is one-call primitive, NOT orchestration framework | CrewAI/AutoGen own that lane; would lose differentiation | 2026-04-15 |
| Default min_relevance for autopilot = 0.05 | Empirically tuned against BM25F cold-start scores | 2026-04-15 |
| Live dashboard uses stdlib `http.server`, not Flask/FastAPI | Zero-dep promise; D3 from CDN is the only external | 2026-04-16 |
| RPG TUI is personal-use, not portfolio-facing | Terminal emoji rendering inconsistent; web is better canvas | 2026-04-16 |
| Roles concept (Phase 1 next) — loadouts become named classes | Moves to category nobody owns: "class system for AI agents" | 2026-04-16 |

---

## Architecture / File Map

```
C:\Claude\ToolMaster\                  github.com/techieharry/ToolMaster (PUBLIC)
├── README.md                          Portfolio-grade landing (60s demo + V1 result)
├── LICENSE                            MIT
├── CLAUDE.md                          Project concept + survival condition
├── ARCHITECTURE.md                    Full system diagram
├── HANDOFF.md                         ← this file
├── TOOLMASTER_AGENT_PROMPT.md         V2 decision tree (auto-distributed by sync)
├── roadmap.md                         Reconciled with code reality
├── pyproject.toml                     `name = "toolmaster"`, console_script wired
├── .env                               OPENROUTER_API_KEY + GITHUB_TOKEN (GITIGNORED)
├── .env.example                       Template for new clones
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
│   ├── scout.py                       GitHub crawl + audit + propose
│   ├── sync.py                        Cross-project harvest + push
│   ├── global_watcher.py              Background daemon
│   ├── trust.py                       External repo trust filter
│   ├── viz.py                         Static D3 HTML generator
│   ├── live.py                        Multi-tab live dashboard server
│   ├── armory.py                      RPG TUI (personal use)
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
    ├── competitive-analysis.md
    ├── immutable-parts.md
    ├── roguelike-selection.md         V2 offer engine design
    └── toolbox-master.md              V3 background job design
```

Profile repo: `C:\Claude\techieharry-profile\` → github.com/techieharry/techieharry (PUBLIC)

---

## State / Config

| Item | Location | Notes |
|---|---|---|
| Global store | `~/.toolmaster/store/` | 11 pinned skills, content-addressed blobs + manifests |
| Recordings | `~/.toolmaster/recordings/` | 7 task recordings (need 50+ for V2 warm path) |
| Loadouts | `~/.toolmaster/loadouts/` | (empty in real store; tests create them in tmp dirs) |
| Proposals | `~/.toolmaster/proposals/` | 27 scout-generated import/extract/reject proposals |
| Scout state | `~/.toolmaster/scout_state.json` | 51 cycles, 442 audited skills, 371 known repos |
| Watcher state | `~/.toolmaster/global_watcher_state.json` | per-project log processing tracking |
| Insights | `~/.toolmaster/global_insights.json` | per-project + per-skill performance metrics |
| Watcher PID | `~/.toolmaster/watcher.pid` | last-known PID; verify process is alive |
| Logs | `~/.toolmaster/{watcher,scout}.log` | now UTF-8 encoded (fixed cp1252 crash) |
| Compare cache | `~/.toolmaster/compare_cache/` | LLM judge results cached by hash |
| API keys | `C:\Claude\ToolMaster\.env` | `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `CLAUDE_DIR` (GITIGNORED) |
| Dashboard port | `localhost:8484` | `toolmaster live --port 8484` |

---

## Dependencies / External Systems

- **Python 3.14** — confirmed working (pure stdlib core; D3 from CDN in viz/live; no pip dependencies in `toolmaster/`)
- **OpenRouter** (preferred) or Anthropic API for: scout audit (Haiku), compare judge (Haiku), delegate dispatch (Haiku/Sonnet), suggest (Haiku), re-engineer (Sonnet)
- **GitHub API** (5000 req/hr authed via `GITHUB_TOKEN` from `.env`)
- **No cloud services** — entirely local, all state in `~/.toolmaster/`
- **`gh` CLI** for GitHub auth and ad-hoc API calls

---

## Known Issues / Gotchas

- **`gh` CLI uses `GH_TOKEN` env (set by `gh auth`) before `GITHUB_TOKEN`.** When overriding tokens for a one-off command, use `GH_TOKEN=...` not `GITHUB_TOKEN=...`. (Cost me 30 minutes earlier this session.)
- **GitHub fine-grained PATs vs classic PATs**: fine-grained PATs (prefix `github_pat_11...`) cannot create repos, change visibility, or update user profile fields. Classic PATs (prefix `ghp_`) with `repo` + `user` scopes can. The default token from `gh auth login` is fine-grained.
- **Pinning repos on a profile has no public API.** Even classic PATs with full scope can't do it. Manual web UI only.
- **Quality gate rejects external skills with critical issues.** Including: missing `description` frontmatter, prompt injection patterns, shell command refs, credential refs. Most external skills from GitHub fail the gate; scout's audit + extract_techniques flow handles this by extracting techniques rather than direct import.
- **`compare_loadouts` silently falls back to heuristic with no API key.** CLI prints `Method: heuristic` — confirm before trusting results.
- **The `toolmaster.lock` file is written to `target_dir.parent`**, not `target_dir`. Correct per code, but worth remembering when debugging apply.
- **Live dashboard graph: drag works only after the `e.sourceEvent.stopPropagation()` fix.** Without it, dragging a node also pans the graph.
- **`pythonw` on Windows buffers stdout aggressively.** Use `-u` flag in any new launcher script (already done in `hooks/run-watcher.ps1`).
- **Many `.read_text()` calls were swept to `encoding="utf-8", errors="replace"` in 2026-04-15.** If you add new file reads, follow the pattern — Windows default cp1252 will crash on real-world content.
- **CLAUDE_DIR is hardcoded in 3 places historically** (global_watcher, scout, sync). All now read from env with `C:/Claude` default. If you fork to another path, set `CLAUDE_DIR` in `.env`.
- **The 11 pinned skills include weak ones like `social-posts` (83% edit, 1 rejection).** Re-engineering pipeline keeps trying to upgrade these but currently fails on the same cp1252 issue. Safe to ignore for now.

---

## Quick-Start for Next Session

```bash
# 1. Verify watcher state
tasklist | grep pythonw                    # Windows
ps aux | grep "toolmaster watch"           # Unix
python -m toolmaster watch --status        # works regardless

# 2. If watcher is dead, restart
bash hooks/run-watcher.sh start            # or powershell hooks/run-watcher.ps1 start

# 3. Open the live dashboard for context
python -m toolmaster live                  # opens http://localhost:8484

# 4. Run tests to confirm clean baseline
python -m unittest tests.test_v1_survival  # should be 46/46 green

# 5. Pull latest if working on different machine
git pull origin main

# 6. Read top 3 priorities in this file's "Next Steps" section
```

For the **Roles** build (top priority next session), start by reading the spec in `Next Steps #1` of this file. Don't start coding until the role-naming taxonomy is decided — it's the load-bearing choice.

---

*This handoff follows the standard template from `C:\Claude\handoff-engine\HANDOFF_TEMPLATE.md`. Updated by the agent at session end on 2026-04-16.*
