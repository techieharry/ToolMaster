"""Loadout system — named, priority-ordered stacks of pinned skill hashes."""

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

from .store import LOADOUTS_DIR, ensure_dirs, get_manifest, resolve_skill


def create_loadout(name: str, skill_hashes: list[str]) -> dict:
    """Create a named loadout from a list of skill hashes (priority order).

    First hash = highest priority.
    """
    ensure_dirs()

    # Validate all hashes exist
    skills = []
    for h in skill_hashes:
        manifest = get_manifest(h)
        skills.append({
            "hash": manifest["id"],
            "name": manifest["name"],
        })

    loadout = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "skills": skills,
    }

    loadout_path = LOADOUTS_DIR / f"{name}.json"
    loadout_path.write_text(json.dumps(loadout, indent=2))
    return loadout


def get_loadout(name: str) -> dict:
    """Get a loadout by name."""
    loadout_path = LOADOUTS_DIR / f"{name}.json"
    if not loadout_path.exists():
        raise FileNotFoundError(f"Loadout not found: {name}")
    return json.loads(loadout_path.read_text())


def list_loadouts() -> list[dict]:
    """List all loadouts."""
    ensure_dirs()
    loadouts = []
    for lf in sorted(LOADOUTS_DIR.glob("*.json")):
        loadout = json.loads(lf.read_text())
        loadouts.append({
            "name": loadout["name"],
            "created_at": loadout["created_at"],
            "skills": len(loadout["skills"]),
            "skill_names": [s["name"] for s in loadout["skills"]],
        })
    return loadouts


def apply_loadout(name: str, target: str = "claude") -> Path:
    """Apply a loadout — resolve skills into agent skill paths.

    Supported targets:
    - "claude": .claude/skills/
    - "agents": .agents/skills/

    Returns the target directory. Writes a toolmaster.lock sidecar.
    """
    loadout = get_loadout(name)

    target_map = {
        "claude": Path.cwd() / ".claude" / "skills",
        "agents": Path.cwd() / ".agents" / "skills",
    }

    if target not in target_map:
        raise ValueError(f"Unknown target: {target}. Use: {list(target_map.keys())}")

    target_dir = target_map[target]
    target_dir.mkdir(parents=True, exist_ok=True)

    # Resolve each skill into the target
    applied = []
    for skill_info in loadout["skills"]:
        skill_path = resolve_skill(skill_info["hash"], target_dir)
        applied.append({
            "name": skill_info["name"],
            "hash": skill_info["hash"],
            "path": str(skill_path),
        })

    # Write toolmaster.lock
    lock = {
        "loadout": name,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "skills": applied,
    }
    lock_path = target_dir.parent / "toolmaster.lock"
    lock_path.write_text(json.dumps(lock, indent=2))

    return target_dir


def diff_loadouts(name_a: str, name_b: str) -> dict:
    """Show differences between two loadouts."""
    a = get_loadout(name_a)
    b = get_loadout(name_b)

    a_skills = {s["hash"]: s["name"] for s in a["skills"]}
    b_skills = {s["hash"]: s["name"] for s in b["skills"]}

    only_a = {h: n for h, n in a_skills.items() if h not in b_skills}
    only_b = {h: n for h, n in b_skills.items() if h not in a_skills}
    shared = {h: n for h, n in a_skills.items() if h in b_skills}

    # Check priority order changes for shared skills
    a_order = [s["hash"] for s in a["skills"]]
    b_order = [s["hash"] for s in b["skills"]]
    order_changed = []
    for h in shared:
        a_idx = a_order.index(h)
        b_idx = b_order.index(h)
        if a_idx != b_idx:
            order_changed.append({
                "name": shared[h],
                "hash": h[:12],
                f"priority_in_{name_a}": a_idx + 1,
                f"priority_in_{name_b}": b_idx + 1,
            })

    return {
        f"only_in_{name_a}": only_a,
        f"only_in_{name_b}": only_b,
        "shared": shared,
        "order_changes": order_changed,
    }
