"""Sync engine — pushes toolbox state and insights back to all projects.

The watcher reads logs. The sync engine writes back:
1. Updated toolbox digest (what tools exist, what's proven)
2. Project-specific recommendations (based on that project's history)
3. Enforces ToolMaster usage via CLAUDE.md injection
4. Keeps TOOLMASTER_AGENT_PROMPT.md current across all projects
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone

from .store import list_skills, pin_skill, TOOLMASTER_HOME
from .suggest import get_proven_skills, _build_performance_index
from .record import list_recordings

# CLAUDE_DIR is the root of the user's projects tree.
# Matches global_watcher.py / scout.py convention: env override with C:/Claude default.
CLAUDE_DIR = Path(os.environ.get("CLAUDE_DIR", "C:/Claude"))
# TOOLMASTER_DIR is the repo itself — self-locate from this file's path so it
# works regardless of where the user cloned it.
TOOLMASTER_DIR = Path(__file__).resolve().parent.parent
PROMPT_SOURCE = TOOLMASTER_DIR / "TOOLMASTER_AGENT_PROMPT.md"
GLOBAL_INSIGHTS_FILE = TOOLMASTER_HOME / "global_insights.json"


def sync_all():
    """Run full sync across all projects.

    Two directions:
    1. PULL: Detect new/updated skills in projects → pin into global toolbox
    2. PUSH: Write digest, update prompts, enforce CLAUDE.md
    """
    projects = _discover_projects()

    # PULL: Harvest new skills from all projects
    harvested = harvest_skills(projects)
    if harvested:
        print(f"  [HARVEST] Pinned {len(harvested)} new/updated skills from projects")
        for h in harvested:
            print(f"    + {h['name']} from {h['project']} ({h['hash'][:12]})")

    # PUSH: Distribute toolbox state back to projects
    digest = _build_toolbox_digest()
    synced = []

    for proj in projects:
        try:
            _sync_project(proj, digest)
            synced.append(proj["name"])
        except Exception as e:
            print(f"  [SYNC ERROR] {proj['name']}: {e}")

    return synced


def harvest_skills(projects: list[dict]) -> list[dict]:
    """Scan all projects for SKILL.md files and pin any that are new or updated.

    This is how agents contribute tools back to the toolbox:
    - Agent working on myagency creates a new skill in skills/email-sequences/SKILL.md
    - Next sync cycle, watcher detects it, pins it to the global store
    - All other projects can now discover and use it via suggest
    """
    existing = {s["name"]: s for s in list_skills()}
    harvested = []

    # Track what we've already harvested to avoid re-pinning unchanged skills
    harvest_state_file = TOOLMASTER_HOME / "harvest_state.json"
    if harvest_state_file.exists():
        harvest_state = json.loads(harvest_state_file.read_text(encoding="utf-8", errors="replace"))
    else:
        harvest_state = {}  # {skill_dir_path: last_mtime}

    for proj in projects:
        proj_path = proj["path"]

        # Look for skills in common locations
        skill_dirs = []

        # skills/ directory (myagency style)
        skills_root = proj_path / "skills"
        if skills_root.is_dir():
            for d in skills_root.iterdir():
                if d.is_dir() and (d / "SKILL.md").exists():
                    skill_dirs.append(d)

        # .claude/skills/ directory (Claude Code native)
        claude_skills = proj_path / ".claude" / "skills"
        if claude_skills.is_dir():
            for d in claude_skills.iterdir():
                if d.is_dir() and (d / "SKILL.md").exists():
                    skill_dirs.append(d)

        # .agents/skills/ directory
        agents_skills = proj_path / ".agents" / "skills"
        if agents_skills.is_dir():
            for d in agents_skills.iterdir():
                if d.is_dir() and (d / "SKILL.md").exists():
                    skill_dirs.append(d)

        for skill_dir in skill_dirs:
            dir_key = str(skill_dir)

            # Check if skill has been modified since last harvest
            try:
                skill_md_mtime = (skill_dir / "SKILL.md").stat().st_mtime
            except OSError:
                continue

            last_harvest = harvest_state.get(dir_key, 0)
            if skill_md_mtime <= last_harvest:
                continue  # Not modified since last harvest

            # Pin the skill
            try:
                manifest = pin_skill(skill_dir)
                harvested.append({
                    "name": manifest["name"],
                    "hash": manifest["id"],
                    "project": proj["name"],
                    "source": str(skill_dir),
                })
                harvest_state[dir_key] = skill_md_mtime
            except Exception as e:
                print(f"  [HARVEST WARN] Failed to pin {skill_dir.name} from {proj['name']}: {e}")

    # Save harvest state
    TOOLMASTER_HOME.mkdir(parents=True, exist_ok=True)
    harvest_state_file.write_text(json.dumps(harvest_state, indent=2))

    return harvested


def _discover_projects() -> list[dict]:
    """Find all projects under Documents/claude/ (excluding ToolMaster)."""
    projects = []
    for d in sorted(CLAUDE_DIR.iterdir()):
        if not d.is_dir() or d.name == "ToolMaster":
            continue
        if (d / "toolmaster").exists() or (d / "TOOLMASTER_AGENT_PROMPT.md").exists():
            projects.append({"name": d.name, "path": d})
    return projects


def _sync_project(proj: dict, digest: dict):
    """Sync toolbox state to a single project."""
    proj_path = proj["path"]

    # 1. Sync TOOLMASTER_AGENT_PROMPT.md (if source is newer)
    _sync_prompt(proj_path)

    # 2. Write toolbox digest (available tools + performance)
    _write_digest(proj_path, digest, proj["name"])

    # 3. Ensure CLAUDE.md has ToolMaster enforcement block
    _enforce_in_claude_md(proj_path)


def _sync_prompt(proj_path: Path):
    """Copy latest TOOLMASTER_AGENT_PROMPT.md if source is newer."""
    target = proj_path / "TOOLMASTER_AGENT_PROMPT.md"
    if not PROMPT_SOURCE.exists():
        return

    if not target.exists():
        shutil.copy2(PROMPT_SOURCE, target)
        return

    # Only copy if source is newer
    if PROMPT_SOURCE.stat().st_mtime > target.stat().st_mtime:
        shutil.copy2(PROMPT_SOURCE, target)


def _build_toolbox_digest() -> dict:
    """Build current state of the toolbox for distribution."""
    all_skills = list_skills()
    recordings = list_recordings()
    performance = _build_performance_index(recordings)
    proven = get_proven_skills(min_uses=2, max_edit_distance=40.0)

    # Load global insights
    insights = {}
    if GLOBAL_INSIGHTS_FILE.exists():
        insights = json.loads(GLOBAL_INSIGHTS_FILE.read_text(encoding="utf-8", errors="replace"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_skills": len(all_skills),
        "total_recordings": len(recordings),
        "skills": [
            {
                "name": s["name"],
                "hash": s["short_id"],
                "files": s["files"],
                "perf": performance.get(s["name"], {}),
            }
            for s in all_skills
        ],
        "proven": proven,
        "insights": {
            "skill_performance": insights.get("skill_performance", {}),
            "action_items": insights.get("action_items", []),
            "v2_ready": insights.get("v2_ready", False),
        },
    }


def _write_digest(proj_path: Path, digest: dict, project_name: str):
    """Write TOOLMASTER_DIGEST.md to the project — human and agent readable."""
    proven_section = ""
    if digest["proven"]:
        rows = []
        for p in digest["proven"]:
            projects = ", ".join(p["projects"]) if p["projects"] else "—"
            rows.append(f"| `{p['name']}` | `{p['hash']}` | {p['times_used']}x | {p['avg_edit_distance']}% | {projects} |")
        proven_section = f"""## Proven tools (low edit distance, multiple uses)

| Skill | Hash | Used | Avg Edit | Projects |
|---|---|---|---|---|
{chr(10).join(rows)}

**Use these first.** They've been tested across projects and produce output that rarely needs editing.
Resolve into your project: `python3 -m toolmaster resolve <hash> ./skills/`
"""

    all_skills_section = ""
    if digest["skills"]:
        rows = []
        for s in digest["skills"]:
            perf = s["perf"]
            used = perf.get("times_used", 0)
            edit = f"{perf['avg_edit_distance']}%" if perf.get("avg_edit_distance") is not None else "—"
            rows.append(f"| `{s['name']}` | `{s['hash']}` | {s['files']} | {used}x | {edit} |")
        all_skills_section = f"""## All tools in the toolbox

| Skill | Hash | Files | Used | Avg Edit |
|---|---|---|---|---|
{chr(10).join(rows)}
"""

    action_section = ""
    if digest["insights"].get("action_items"):
        items = "\n".join(f"- {item}" for item in digest["insights"]["action_items"])
        action_section = f"""## Action items from the watcher

{items}
"""

    content = f"""# ToolMaster Toolbox Digest

> Auto-generated by ToolMaster watcher. Do not edit manually.
> Last updated: {digest['generated_at'][:19]}Z
> Total skills: {digest['total_skills']} | Total recordings: {digest['total_recordings']}

{proven_section}
{all_skills_section}
{action_section}
## Quick commands

```bash
# Find the right tool for your task
python3 -m toolmaster suggest "what you need to do"

# See proven tools
python3 -m toolmaster suggest --proven

# Resolve a tool into this project
python3 -m toolmaster resolve <hash> ./skills/

# Apply a full loadout
python3 -m toolmaster loadout apply <name>
```
"""

    digest_path = proj_path / "TOOLMASTER_DIGEST.md"
    digest_path.write_text(content)


PROJECT_LOADOUT_MAP = {
    "PSX Pulse": "psx-pulse",
    "Wife dashboard": "wife-dashboard",
    "Virtual_Controller": "virtual-controller",
    "WhisperHotkey": "whisper-hotkey",
    "theforge": "theforge",
    "Immigration": "immigration",
    "Fawad_Immigration_Case": "immigration",
    "myagency": "restaurant-client",
    "Career_Pathway_Analysis": "immigration",
    "Claude Usage Tracker": "dev-universal",
    "health insurance": "immigration",
    "IELTS AI": "immigration",
}


def _enforce_in_claude_md(proj_path: Path):
    """Ensure project's CLAUDE.md includes ToolMaster enforcement block.

    Tailored per project — each gets its specific loadout and relevant tools.
    """
    claude_md = proj_path / "CLAUDE.md"
    if not claude_md.exists():
        return

    content = claude_md.read_text(encoding="utf-8", errors="replace")
    project_name = proj_path.name
    loadout_name = PROJECT_LOADOUT_MAP.get(project_name, "dev-universal")

    ENFORCE_MARKER = "<!-- TOOLMASTER_ENFORCE -->"

    block = _enforcement_block(project_name, loadout_name)

    if ENFORCE_MARKER in content:
        before = content.split(ENFORCE_MARKER)[0]
        content = before + block
    else:
        content = content.rstrip() + "\n\n" + block

    claude_md.write_text(content, encoding="utf-8")


def _enforcement_block(project_name: str = "", loadout_name: str = "dev-universal") -> str:
    """Generate project-specific enforcement block for CLAUDE.md."""
    from .loadout import get_loadout
    from .store import get_manifest

    # Get this project's loadout skills
    loadout_section = ""
    try:
        lo = get_loadout(loadout_name)
        skill_lines = []
        for s in lo["skills"]:
            manifest = get_manifest(s["hash"])
            skill_md = manifest["files"].get("SKILL.md")
            desc = ""
            if skill_md:
                from .store import read_blob
                content = read_blob(skill_md["hash"]).decode("utf-8", errors="replace")
                for line in content.split("\n")[:10]:
                    if line.strip().startswith("description:"):
                        desc = line.strip()[12:].strip().strip('"').strip("'")[:100]
                        break
            skill_lines.append(f"  - `{s['name']}` ({s['hash'][:12]}) — {desc}")
        loadout_section = f"\n\nYour loadout (`{loadout_name}`):\n" + "\n".join(skill_lines)
    except FileNotFoundError:
        loadout_section = f"\n\nDefault loadout: `{loadout_name}` (run: `python3 -m toolmaster loadout apply {loadout_name}`)"

    proven = get_proven_skills(min_uses=2, max_edit_distance=40.0)
    proven_list = ""
    if proven:
        seen = {}
        for p in proven:
            if p["name"] not in seen:
                seen[p["name"]] = p
        proven_list = "\n".join(
            f"  - `{p['name']}` ({p['hash']}) — {p['times_used']}x used, {p['avg_edit_distance']}% edit"
            for p in list(seen.values())[:10]
        )
        proven_list = f"\n\nProven tools across all projects:\n{proven_list}"

    return f"""<!-- TOOLMASTER_ENFORCE -->
## ToolMaster Protocol (auto-managed, mandatory)

You MUST follow this protocol every session. ToolMaster tracks compliance.

### Session start
```bash
python3 -m toolmaster checkin
```
This registers your session and shows you proven tools + proposals.

### Before building ANYTHING from scratch
```bash
python3 -m toolmaster checkout "describe what you need"
```
This checks the global toolbox. If a proven tool exists, USE IT:
```bash
python3 -m toolmaster resolve <hash> ./skills/
python3 -m toolmaster used <skill-name> <hash> --task "what you used it for"
```

### When you create a new tool
```bash
python3 -m toolmaster created ./skills/new-skill/ --task "why you built it"
```
This auto-pins it to the global toolbox for other projects to discover.

### When you improve/fork an existing tool
```bash
python3 -m toolmaster forked ./skills/improved-skill/ <parent-hash> --task "why" --changes "what changed"
```
This tracks lineage — the watcher knows this is v2 of a specific tool.

### Session end
```bash
python3 -m toolmaster return
```
This archives your session and reports compliance score.

### Also: log generation runs to data/logs/ (see TOOLMASTER_AGENT_PROMPT.md)

### Apply your loadout
```bash
python3 -m toolmaster loadout apply {loadout_name}
```

Read `TOOLMASTER_DIGEST.md` for full toolbox state and performance data.
{loadout_section}
{proven_list}
<!-- /TOOLMASTER_ENFORCE -->
"""
