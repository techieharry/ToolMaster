# ToolMaster Integration — drop this into any Claude Code session

This project has ToolMaster installed (`./toolmaster/` symlinked from `~/Documents/claude/ToolMaster/toolmaster/`). ToolMaster is a content-addressed skill registry, loadout system, and skill dispatch layer that tracks AI quality across all projects and delegates well-scoped tasks to specialist agents.

**If you are an agent reading this file, this is your operating manual. Read the "Decision tree" section first — it tells you when to reach for ToolMaster vs when to do the work inline yourself.**

---

## Decision tree: when to use ToolMaster

```
Task arrives
   │
   ├─ Is it well-scoped? (fits in 1-3 sentences, doesn't need full project context)
   │     NO  → do it inline yourself
   │     YES → continue
   │
   ├─ Is there a matching loadout in the store?
   │     Run:  python3 -m toolmaster offer "<task description>"
   │     │
   │     ├─ Got a confident canonical (relevance > 0.3)?
   │     │     YES → delegate it:
   │     │            python3 -m toolmaster delegate "<task>" --loadout <name> -y
   │     │            (or one-shot: python3 -m toolmaster autopilot "<task>" -y)
   │     │     NO  → do it inline, then AFTER finishing, record the task
   │     │            so the flywheel learns a new pattern:
   │     │            python3 -m toolmaster record -t "<task>" -o "<result>" -l <loadout-or-none>
```

**Rule of thumb**: if the task is something you'd hand to a junior developer with a written-down procedure (refactor, reformat, bug fix, write tests, review code, extract function, etc.), it's a delegate candidate. If it needs creative judgment about the project's architecture, competitive strategy, or business goals, do it inline.

---

## V2 commands (start here — these are the primary verbs)

### `offer` — "what loadout fits this task?"

```bash
python3 -m toolmaster offer "refactor the long handler in api.py"
```

Returns up to 3 offers:
- **canonical** — top-ranked loadout by description fit + outcome win rate
- **iterated** — canonical's close cousin with a proposed skill tweak
- **sideways** — compositionally different option in case canonical misses

Each offer has a `relevance` score, a reason sentence, and a `cold_start` flag. If `cold_start: true`, the ranking is pure description fit; if `false`, it's weighted by real recorded outcomes (needs ≥50 recordings).

### `delegate` — "have a specialist do this"

```bash
python3 -m toolmaster delegate "refactor the long handler in api.py" \
    --loadout refactor_stack -y
```

What happens:
1. Resolves the loadout into a specialist system prompt (skills loaded in priority order)
2. Shows cost estimate before any API call
3. Calls Haiku 4.5 (or Sonnet with `--model anthropic/claude-sonnet-4`)
4. Captures output
5. Writes a `[delegate]`-tagged recording so the flywheel learns
6. Returns result text to stdout — nothing is written to your workspace

Flags:
- `--dry-run` → shows cost estimate without calling the API
- `-y` / `--yes` → skips the interactive confirmation (use this when agents invoke it)
- `--model <name>` → override the default Haiku model
- `--no-record` → skip writing a recording (for debug/exploration)

**When to delegate**: well-scoped subtask that the primary agent would otherwise do inline with a much larger context window. The specialist runs ~10-50× cheaper than Sonnet-inline.

**When NOT to delegate**: task needs project-wide reasoning, cross-file refactors, or creative judgment. Delegate a *subtask*, not an *entire feature*.

### `autopilot` — "offer + delegate in one call"

```bash
python3 -m toolmaster autopilot "refactor the long handler" -y
```

Runs `offer` internally, picks the canonical result, then delegates to it. For when you trust the offer engine's top choice and want a single verb. Safest to run with `--dry-run` first if you're unsure.

---

## Core session protocol (auto-called by hooks, but you can call manually)

### Phase 1: `checkin` — see what's in the toolbox

```bash
python3 -m toolmaster checkin
```

Returns toolbox state: pinned skills, proven skills (low edit distance, multi-project use), all loadouts, active proposals from the scout. Call at session start. The hook usually does this automatically via `hooks/session-start.sh`.

### Phase 2: `checkout` — "do I already have a tool for this?"

```bash
python3 -m toolmaster checkout "write a failing test for the off-by-one bug"
```

Returns relevant skills AND loadout offers for the task. This is the V1 version of the decision tree — use it when you need a richer context than `offer` alone.

### Phase 3: Track what you used

```bash
# You used an existing toolbox skill
python3 -m toolmaster used <skill-name> <hash> --task "..." --outcome used_as_is

# You built a new skill because none existed
python3 -m toolmaster created ./skills/new-thing --task "..." --reason no_existing_tool

# You forked and improved an existing skill
python3 -m toolmaster forked ./skills/improved --parent <hash> --task "..." --changes "..."
```

### Phase 4: `return` — end session

```bash
python3 -m toolmaster return
```

Archives the session, scores compliance (did you check before building?), and returns tools to the toolbox. Usually called automatically by the stop hook.

---

## Recording format (for manual logs)

If you're not using the protocol commands and just want to log a run manually:

```bash
cat > data/logs/gen_$(date +%s).json << 'EOF'
{
  "business_name": "CLIENT_OR_PROJECT_NAME",
  "client_type": "restaurant|saas|freelancer|ecommerce|local-service|general",
  "loadout": "loadout-name-used",
  "deliverables_generated": ["skill-name-1", "skill-name-2"],
  "sections": {
    "skill-name-1": {
      "raw_output": "what AI generated initially",
      "final_output": "what was actually delivered after edits (null if unchanged)",
      "status": "approved|rejected|regenerated|pending",
      "reviewed_at": "2026-04-11T10:00:00+00:00"
    }
  },
  "generated_at": "2026-04-11T10:00:00+00:00",
  "client_rating": null,
  "owner_notes": "observations about quality"
}
EOF
```

The watcher auto-harvests these from `data/logs/*.json` across all projects.

### Field guide

| Field | Required | Notes |
|---|---|---|
| `business_name` | Yes | Client or project identifier |
| `client_type` | Yes | Category for loadout routing |
| `loadout` | Yes | Which loadout was used (or "none") |
| `deliverables_generated` | Yes | List of skill names that ran |
| `sections` | Yes | Per-skill output tracking |
| `generated_at` | Yes | ISO 8601 timestamp |
| `client_rating` | No | 1-5 end-client satisfaction |
| `owner_notes` | No | Free text |

### What matters for quality tracking

- **`raw_output` vs `final_output`** — the edit distance is the primary quality signal
- **`status: rejected`** — counts as 100% edit distance, strong signal the skill needs improvement
- **Approval speed** — `reviewed_at` − `generated_at` = how fast the output was accepted

---

## Full command reference

```bash
# V2 (new — primary verbs for autonomous agents)
python3 -m toolmaster offer "<task>"                          # rank loadouts
python3 -m toolmaster delegate "<task>" --loadout <name> -y   # dispatch specialist
python3 -m toolmaster autopilot "<task>" -y                   # offer + delegate in one

# Store
python3 -m toolmaster ls                           # list pinned skills
python3 -m toolmaster pin <skill-dir>              # pin a new skill
python3 -m toolmaster show <hash>                  # skill details
python3 -m toolmaster resolve <hash> <target>      # reconstruct from store

# Loadouts
python3 -m toolmaster loadout list
python3 -m toolmaster loadout show <name>
python3 -m toolmaster loadout create <name> <hash1> <hash2> ...
python3 -m toolmaster loadout apply <name> --target claude   # or cursor/codex/aider/...
python3 -m toolmaster loadout diff <A> <B>

# Evaluation
python3 -m toolmaster compare <A> <B>              # LLM judge (needs OPENROUTER_API_KEY)
python3 -m toolmaster compare <A> <B> --heuristic  # offline ranking
python3 -m toolmaster suggest "<task>"             # individual skill suggestions
python3 -m toolmaster suggest --proven             # proven skills only

# Recording
python3 -m toolmaster record -t "..." -l <loadout> -r 4    # manual record
python3 -m toolmaster recordings                           # list

# Protocol (session lifecycle, usually auto-called)
python3 -m toolmaster checkin
python3 -m toolmaster checkout "<task>"
python3 -m toolmaster used <skill> <hash> --task "..." --outcome used_as_is
python3 -m toolmaster created <skill-dir> --task "..." --reason no_existing_tool
python3 -m toolmaster forked <skill-dir> <parent-hash> --task "..." --changes "..."
python3 -m toolmaster return

# Autonomous layer
python3 -m toolmaster scout                # one scout cycle (needs OPENROUTER_API_KEY)
python3 -m toolmaster watch --status       # global insights
python3 -m toolmaster watch --once         # one watcher cycle
```

---

## How it all connects

```
You do work in this project
        ↓
Hooks write logs to data/logs/*.json
        ↓
Global watcher (pythonw daemon) reads the logs
        ↓
Extracts edit-distance / rating / rejection signals
        ↓
Records in ~/.toolmaster/store
        ↓
V2 offer engine ranks loadouts by real outcomes
        ↓
Next task → toolmaster offer → pick one → delegate → result
        ↓
That result is ALSO recorded → flywheel closes, data compounds
        ↓
Scout pulls new skills from GitHub in the background → proposals queue
```

**The flywheel is real**. Every delegate call, every recorded task, every scout cycle adds a data point that makes the next recommendation better.

---

## IMPORTANT: Before building from scratch, check the toolbox

Another project may have already built and proven a skill for what you need. Before writing new generation logic:

```bash
python3 -m toolmaster offer "describe what you need to do"          # loadout level (preferred)
python3 -m toolmaster suggest "describe what you need to do"        # individual skill level
python3 -m toolmaster suggest --proven                              # only battle-tested skills
```

If a skill like `strategy-doc` has 0% edit distance across 6 runs in 3 projects, USE IT instead of writing a new strategy generator. If `social-posts` has 83% edit distance, AVOID IT or fork-and-improve it with `toolmaster forked`.

---

*Just write logs, check before building, delegate well-scoped subtasks. The watcher and scout handle the rest.*
