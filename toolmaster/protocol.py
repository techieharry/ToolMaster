"""ToolMaster Agent Protocol — the structured interface between agents and the toolbox.

Every agent session reads and writes to a session manifest. This is how ToolMaster
KNOWS what agents are doing, not hopes they'll log voluntarily.

The protocol has 4 phases:
1. CHECKIN  — agent starts, reads toolbox state, declares intent
2. CHECKOUT — agent checks if relevant tools exist before building
3. WORKLOG  — agent reports what it used, built, forked, improved
4. RETURN   — agent returns new/improved tools to the toolbox

The session manifest lives at data/toolmaster_session.json in each project.
The watcher reads these manifests — they're the source of truth.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from .store import list_skills, get_manifest, pin_skill, TOOLMASTER_HOME
from .suggest import suggest, get_proven_skills
from .loadout import list_loadouts


def checkin(project_dir: str | Path) -> dict:
    """Phase 1: Agent checks in. Returns toolbox state for the agent to consume.

    The agent MUST call this at session start. It returns:
    - All available tools with performance data
    - Proven tools (battle-tested)
    - Active proposals from the watcher
    - What this project has used before
    """
    project_dir = Path(project_dir)
    manifest_path = project_dir / "data" / "toolmaster_session.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Load proposals if any
    proposals = _load_proposals(project_dir)

    # Loadouts available for delegation
    try:
        loadouts = list_loadouts()
    except Exception:
        loadouts = []

    # Build checkin response
    state = {
        "protocol_version": "1.1",
        "checked_in_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.name,
        "toolbox": {
            "total_skills": len(list_skills()),
            "proven": [
                {"name": p["name"], "hash": p["hash"], "used": p["times_used"], "edit": p["avg_edit_distance"]}
                for p in get_proven_skills(min_uses=2, max_edit_distance=40.0)
            ],
            "loadouts": [
                {"name": lo["name"], "skills": lo["skill_names"], "skill_count": lo["skills"]}
                for lo in loadouts
            ],
        },
        "proposals": proposals,
        "session": {
            "tools_checked": [],
            "tools_used": [],
            "tools_created": [],
            "tools_forked": [],
            "tools_improved": [],
            "tools_rejected": [],
            "tasks_completed": [],
        },
        "status": "active",
    }

    manifest_path.write_text(json.dumps(state, indent=2))
    return state


def checkout(project_dir: str | Path, task_description: str) -> dict:
    """Phase 2: Agent checks if tools exist for a task before building.

    Returns both individual skill suggestions AND V2 loadout offers, so the
    agent can decide whether to compose from skills or delegate to a full
    loadout. Records that the check happened.
    """
    project_dir = Path(project_dir)
    manifest = _load_manifest(project_dir)

    # Individual skill suggestions (V1 path)
    suggestions = suggest(task_description, top_n=5, use_llm=False)

    # V2 loadout offers — only try if loadouts exist, otherwise offer() returns []
    try:
        from .offer import suggest_loadouts
        loadout_offers = suggest_loadouts(task_description, top_n=3)
    except Exception:
        loadout_offers = []

    # Record the checkout
    manifest["session"]["tools_checked"].append({
        "task": task_description,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "suggestions_returned": len(suggestions),
        "loadout_offers_returned": len(loadout_offers),
        "top_suggestion": suggestions[0]["name"] if suggestions else None,
        "top_score": suggestions[0].get("relevance_score", 0) if suggestions else 0,
        "top_loadout": loadout_offers[0]["name"] if loadout_offers else None,
        "top_loadout_relevance": loadout_offers[0]["relevance"] if loadout_offers else 0,
    })

    _save_manifest(project_dir, manifest)

    return {
        "task": task_description,
        "suggestions": [
            {
                "name": s["name"],
                "hash": s["short_hash"],
                "score": s.get("relevance_score", 0),
                "edit_distance": s["performance"]["avg_edit_distance"],
                "times_used": s["performance"]["times_used"],
                "description": s["description"][:200],
            }
            for s in suggestions
        ],
        "loadout_offers": [
            {
                "type": o["type"],
                "name": o["name"],
                "skills": o["skills"],
                "relevance": o["relevance"],
                "reason": o["reason"],
                "cold_start": o["cold_start"],
            }
            for o in loadout_offers
        ],
    }


def log_tool_used(project_dir: str | Path, skill_name: str, skill_hash: str,
                  task: str, outcome: str = "used_as_is") -> dict:
    """Phase 3a: Agent reports using an existing tool from the toolbox.

    Outcomes: used_as_is, modified_slightly, heavily_modified, rejected
    """
    project_dir = Path(project_dir)
    manifest = _load_manifest(project_dir)

    entry = {
        "skill": skill_name,
        "hash": skill_hash,
        "task": task,
        "outcome": outcome,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest["session"]["tools_used"].append(entry)
    _save_manifest(project_dir, manifest)
    return entry


def log_tool_created(project_dir: str | Path, skill_dir: str | Path,
                     task: str, reason: str = "no_existing_tool") -> dict:
    """Phase 3b: Agent reports creating a brand new tool.

    Reasons: no_existing_tool, existing_too_generic, completely_new_domain
    """
    project_dir = Path(project_dir)
    manifest = _load_manifest(project_dir)

    # Auto-pin the new skill
    try:
        skill_manifest = pin_skill(skill_dir)
        pinned_hash = skill_manifest["id"]
        pinned_name = skill_manifest["name"]
    except Exception as e:
        pinned_hash = None
        pinned_name = str(Path(skill_dir).name)

    entry = {
        "skill": pinned_name,
        "hash": pinned_hash,
        "source_dir": str(skill_dir),
        "task": task,
        "reason": reason,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "forked_from": None,
    }
    manifest["session"]["tools_created"].append(entry)
    _save_manifest(project_dir, manifest)
    return entry


def log_tool_forked(project_dir: str | Path, new_skill_dir: str | Path,
                    parent_hash: str, task: str, changes: str = "") -> dict:
    """Phase 3c: Agent reports forking/improving an existing tool.

    This is how we track lineage — new_skill was derived from parent_hash.
    """
    project_dir = Path(project_dir)
    manifest = _load_manifest(project_dir)

    # Pin the forked skill
    try:
        skill_manifest = pin_skill(new_skill_dir)
        new_hash = skill_manifest["id"]
        new_name = skill_manifest["name"]
    except Exception as e:
        new_hash = None
        new_name = str(Path(new_skill_dir).name)

    entry = {
        "skill": new_name,
        "new_hash": new_hash,
        "parent_hash": parent_hash,
        "source_dir": str(new_skill_dir),
        "task": task,
        "changes": changes,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest["session"]["tools_forked"].append(entry)

    # Record lineage in the store
    _record_lineage(new_hash, parent_hash, new_name, changes)

    _save_manifest(project_dir, manifest)
    return entry


def return_tools(project_dir: str | Path) -> dict:
    """Phase 4: Session end — summarize what happened and return tools to toolbox.

    The watcher reads this to understand what the agent did.
    """
    project_dir = Path(project_dir)
    manifest = _load_manifest(project_dir)

    session = manifest["session"]
    summary = {
        "project": manifest["project"],
        "checked_in_at": manifest["checked_in_at"],
        "returned_at": datetime.now(timezone.utc).isoformat(),
        "tools_checked": len(session["tools_checked"]),
        "tools_used": len(session["tools_used"]),
        "tools_created": len(session["tools_created"]),
        "tools_forked": len(session["tools_forked"]),
        "tasks_completed": len(session["tasks_completed"]),
        "checked_before_building": _compliance_score(session),
    }

    manifest["status"] = "returned"
    manifest["summary"] = summary
    _save_manifest(project_dir, manifest)

    # Archive the session
    archive_dir = project_dir / "data" / "sessions"
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = archive_dir / f"session_{ts}.json"
    archive_path.write_text(json.dumps(manifest, indent=2))

    return summary


def _compliance_score(session: dict) -> float:
    """How well did the agent follow the protocol?

    1.0 = checked suggest before every creation
    0.0 = built everything from scratch without checking
    """
    created = len(session["tools_created"])
    forked = len(session["tools_forked"])
    total_built = created + forked

    if total_built == 0:
        return 1.0  # Didn't build anything, used existing tools

    checked = len(session["tools_checked"])
    if checked == 0 and total_built > 0:
        return 0.0  # Built without checking

    # Score based on ratio of checks to builds
    return min(1.0, round(checked / max(total_built, 1), 2))


def _load_manifest(project_dir: Path) -> dict:
    manifest_path = project_dir / "data" / "toolmaster_session.json"
    if not manifest_path.exists():
        return checkin(project_dir)
    return json.loads(manifest_path.read_text())


def _save_manifest(project_dir: Path, manifest: dict):
    manifest_path = project_dir / "data" / "toolmaster_session.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))


def _load_proposals(project_dir: Path) -> list:
    """Load watcher proposals for this project."""
    proposals_file = project_dir / "data" / "toolmaster_proposals.json"
    if proposals_file.exists():
        return json.loads(proposals_file.read_text())
    return []


def _record_lineage(new_hash: str, parent_hash: str, name: str, changes: str):
    """Record skill lineage in the global store."""
    lineage_file = TOOLMASTER_HOME / "lineage.json"
    if lineage_file.exists():
        lineage = json.loads(lineage_file.read_text())
    else:
        lineage = {}

    if new_hash:
        lineage[new_hash] = {
            "parent": parent_hash,
            "name": name,
            "changes": changes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    lineage_file.write_text(json.dumps(lineage, indent=2))
