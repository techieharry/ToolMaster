# ToolMaster Integration — Paste this into any Claude Code session

This project has ToolMaster installed (`./toolmaster/` symlinked from `~/Documents/claude/ToolMaster/toolmaster/`). ToolMaster is a content-addressed skill registry and loadout system that tracks AI generation quality across all projects.

## Logging generation runs

When you complete a generation or significant AI task in this project, write a log file to `data/logs/`:

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
    },
    "skill-name-2": {
      "raw_output": "initial output",
      "final_output": null,
      "status": "approved",
      "reviewed_at": "2026-04-11T10:05:00+00:00"
    }
  },
  "generated_at": "2026-04-11T10:00:00+00:00",
  "generation_time_seconds": 30,
  "client_rating": null,
  "owner_notes": "any observations about quality, what worked, what didn't"
}
EOF
```

### Field guide

| Field | Required | Notes |
|---|---|---|
| `business_name` | Yes | Client name or project identifier |
| `client_type` | Yes | Category for loadout routing |
| `loadout` | Yes | Which ToolMaster loadout was used (or "none") |
| `deliverables_generated` | Yes | List of skill names that ran |
| `sections` | Yes | Per-skill output tracking (see below) |
| `generated_at` | Yes | ISO 8601 timestamp when generation started |
| `generation_time_seconds` | No | How long generation took |
| `client_rating` | No | 1-5 end-client satisfaction (null if unknown) |
| `owner_notes` | No | Free text — what worked, what needed fixing |

### Section status values

| Status | Meaning |
|---|---|
| `approved` | Output used as-is or with minor edits |
| `rejected` | Output thrown away entirely |
| `regenerated` | Output re-run with different prompt/approach |
| `pending` | Not yet reviewed |

### What matters for quality tracking

- **`raw_output` vs `final_output`**: The edit distance between these is the primary quality signal. If `final_output` is null and status is "approved", ToolMaster assumes 0% edit (output was perfect).
- **`status: rejected`**: Counts as 100% edit distance. This is a strong signal that the skill needs improvement.
- **`reviewed_at`**: Time between `generated_at` and last `reviewed_at` = approval speed. Fast approval = good output.

## Available commands

Run from the project root:

```bash
# List all pinned skills in the store
python3 -m toolmaster ls

# Pin a new skill directory
python3 -m toolmaster pin <skill-dir>

# Show skill details (accepts hash prefix)
python3 -m toolmaster show <hash>

# List available loadouts
python3 -m toolmaster loadout list

# Show a loadout's contents
python3 -m toolmaster loadout show <name>

# Apply a loadout — injects skills into .claude/skills/
python3 -m toolmaster loadout apply <name>

# Diff two loadouts
python3 -m toolmaster loadout diff <A> <B>

# Quick-record a task manually
python3 -m toolmaster record -t "task description" -l loadout-name -r 4

# List all recordings
python3 -m toolmaster recordings

# Compare two loadouts (needs OPENROUTER_API_KEY for LLM judge)
OPENROUTER_API_KEY="..." python3 -m toolmaster compare <A> <B>

# Compare with heuristic (no API key needed)
python3 -m toolmaster compare <A> <B> --heuristic

# Check global insights across all projects
python3 -m toolmaster watch --status

# Run global watcher once
python3 -m toolmaster watch --once
```

## IMPORTANT: Before generating from scratch, check the toolbox

Other projects may have already built and proven a skill for what you need. Before writing new generation logic, run:

```bash
# "Do I already have a tool for this?"
python3 -m toolmaster suggest "describe what you need to do"

# "What tools are proven to work well?"
python3 -m toolmaster suggest --proven

# Found a useful skill? Resolve it into your project:
python3 -m toolmaster resolve <hash> ./skills/

# Or see all available skills:
python3 -m toolmaster ls
```

**This is how you save tokens.** If `strategy-doc` has 0% edit distance across 6 runs in 3 projects, USE IT instead of writing a new strategy generator. If `social-posts` has 83% edit distance, AVOID IT or improve it.

The suggest command ranks skills by:
- Keyword relevance to your task
- Performance data (edit distance, rejection rate) from all projects
- How many times the skill has been used and where

## How it all connects

```
You write logs to data/logs/*.json
        ↓
Global watcher picks them up (runs from ToolMaster project)
        ↓
Extracts quality signals (edit distance, rejection rate, approval time)
        ↓
Records in ToolMaster store
        ↓
toolmaster suggest uses this data to recommend proven skills
        ↓
Other projects reuse what works → fewer tokens, better output
        ↓
At 50+ runs per loadout → V2 iteration triggers
```

Just write the logs. Check suggest before building. The watcher handles the rest.
