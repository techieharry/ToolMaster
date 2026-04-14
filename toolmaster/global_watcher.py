"""Global watcher — monitors all projects under Documents/claude/ for generation logs.

Polls data/logs/ in every project folder, extracts signals, records in ToolMaster,
and aggregates cross-project insights for V2 iteration.
"""

import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# ToolMaster imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from toolmaster import record as tm_record
from toolmaster.store import TOOLMASTER_HOME, ensure_dirs

CLAUDE_DIR = Path(os.environ.get("CLAUDE_DIR", "C:/Claude"))
GLOBAL_STATE_FILE = TOOLMASTER_HOME / "global_watcher_state.json"
GLOBAL_INSIGHTS_FILE = TOOLMASTER_HOME / "global_insights.json"
HANDOFF_STALE_HOURS = 2  # Report handoff as stale if older than this


def _load_state() -> dict:
    """Load processed log tracking state."""
    ensure_dirs()
    if GLOBAL_STATE_FILE.exists():
        return json.loads(GLOBAL_STATE_FILE.read_text())
    return {"processed": {}}


def _save_state(state: dict):
    state_path = GLOBAL_STATE_FILE
    state_path.write_text(json.dumps(state, indent=2))


def _compute_edit_distance(raw: str, final: str) -> float:
    """Compute edit distance as percentage changed."""
    if not raw or not final:
        return 0.0
    import difflib
    ratio = difflib.SequenceMatcher(None, raw, final).ratio()
    return round((1 - ratio) * 100, 1)


def discover_projects() -> list[dict]:
    """Find all projects with data/logs/ directories."""
    projects = []
    for d in sorted(CLAUDE_DIR.iterdir()):
        if not d.is_dir() or d.name == "ToolMaster":
            continue
        logs_dir = d / "data" / "logs"
        if logs_dir.exists():
            projects.append({
                "name": d.name,
                "path": str(d),
                "logs_dir": str(logs_dir),
            })
    return projects


def check_handoff_health() -> dict:
    """Check HANDOFF.md status across all projects. Lightweight — no enforcement."""
    skip = {"scripts", ".git", "ToolMaster"}
    results = {"missing": [], "stale": [], "ok": [], "total": 0}
    now = time.time()
    stale_threshold = HANDOFF_STALE_HOURS * 3600

    for d in sorted(CLAUDE_DIR.iterdir()):
        if not d.is_dir() or d.name in skip:
            continue
        results["total"] += 1
        handoff = d / "HANDOFF.md"
        if not handoff.exists():
            results["missing"].append(d.name)
        else:
            age = now - handoff.stat().st_mtime
            if age > stale_threshold:
                hours = int(age / 3600)
                results["stale"].append({"name": d.name, "hours": hours})
            else:
                results["ok"].append(d.name)
    return results


def scan_logs(projects: list[dict], state: dict) -> list[dict]:
    """Scan all projects for unprocessed logs."""
    new_logs = []
    for proj in projects:
        logs_dir = Path(proj["logs_dir"])
        processed_for_project = state["processed"].get(proj["name"], [])

        for log_file in sorted(logs_dir.glob("*.json")):
            log_id = f"{proj['name']}/{log_file.stem}"
            if log_id in processed_for_project:
                continue
            try:
                log_data = json.loads(log_file.read_text())
                log_data["_project"] = proj["name"]
                log_data["_log_id"] = log_id
                log_data["_file"] = str(log_file)
                new_logs.append(log_data)
            except json.JSONDecodeError:
                print(f"  [WARN] Malformed: {log_file}")

    return new_logs


def process_log(log: dict) -> dict:
    """Process a single log → extract signals → record in ToolMaster."""
    project = log["_project"]
    log_id = log["_log_id"]

    # Extract basic info
    client_type = log.get("client_type", "unknown")
    loadout = log.get("loadout", "unknown")
    business = log.get("business_name", "unknown")
    deliverables = log.get("deliverables_generated", [])

    # Extract quality signals
    sections = log.get("sections", {})
    edit_distances = {}
    statuses = {}
    for name, section in sections.items():
        raw = section.get("raw_output", "")
        final = section.get("final_output")
        status = section.get("status", "unknown")
        statuses[name] = status

        if status == "rejected":
            edit_distances[name] = 100.0
        elif raw and final:
            edit_distances[name] = _compute_edit_distance(raw, final)
        elif status == "approved" and not final:
            edit_distances[name] = 0.0

    avg_edit = round(sum(edit_distances.values()) / len(edit_distances), 1) if edit_distances else None
    rejections = sum(1 for s in statuses.values() if s in ("rejected", "regenerated"))
    rejection_rate = round(rejections / len(statuses) * 100, 1) if statuses else None

    # Time to approve
    approve_time = None
    gen_at = log.get("generated_at")
    review_times = [s.get("reviewed_at") for s in sections.values() if s.get("reviewed_at")]
    if gen_at and review_times:
        try:
            gen_dt = datetime.fromisoformat(gen_at)
            last_review = max(datetime.fromisoformat(t) for t in review_times)
            approve_time = round((last_review - gen_dt).total_seconds() / 60, 1)
        except (ValueError, TypeError):
            pass

    # Build signal summary
    signals = {
        "project": project,
        "client_type": client_type,
        "loadout": loadout,
        "edit_distances": edit_distances,
        "avg_edit_distance": avg_edit,
        "rejection_rate": rejection_rate,
        "time_to_approve_min": approve_time,
        "client_rating": log.get("client_rating"),
        "generation_time_seconds": log.get("generation_time_seconds"),
        "owner_notes": log.get("owner_notes"),
    }

    # Compute rating
    score = 3.0
    if avg_edit is not None:
        if avg_edit < 10: score += 1.0
        elif avg_edit < 30: score += 0.5
        elif avg_edit > 60: score -= 1.0
    if rejection_rate and rejection_rate > 40: score -= 1.0
    if log.get("client_rating"): score = (score + log["client_rating"]) / 2
    rating = max(1, min(5, round(score)))

    # Record in ToolMaster
    task_desc = f"[{project}][{client_type}] {business} — {', '.join(deliverables)}"
    recording = tm_record.quick_record(
        task=task_desc,
        output=json.dumps(signals, indent=2),
        loadout_name=loadout,
        rating=rating,
    )

    return {
        "log_id": log_id,
        "project": project,
        "recording_id": recording["id"],
        "signals": signals,
        "rating": rating,
    }


def update_global_insights(results: list[dict]):
    """Update cross-project insights."""
    ensure_dirs()

    if GLOBAL_INSIGHTS_FILE.exists():
        insights = json.loads(GLOBAL_INSIGHTS_FILE.read_text())
    else:
        insights = {
            "total_runs": 0,
            "runs_by_project": {},
            "runs_by_loadout": {},
            "skill_performance": {},
            "project_health": {},
            "v2_candidates": [],
            "action_items": [],
            "last_updated": None,
        }

    for result in results:
        sig = result["signals"]
        project = result["project"]
        loadout = sig.get("loadout", "unknown")

        insights["total_runs"] += 1

        # Per-project tracking
        if project not in insights["runs_by_project"]:
            insights["runs_by_project"][project] = {"count": 0, "avg_edit": [], "ratings": []}
        proj_data = insights["runs_by_project"][project]
        proj_data["count"] += 1
        if sig.get("avg_edit_distance") is not None:
            proj_data["avg_edit"].append(sig["avg_edit_distance"])
        if sig.get("client_rating") is not None:
            proj_data["ratings"].append(sig["client_rating"])

        # Per-loadout tracking
        if loadout not in insights["runs_by_loadout"]:
            insights["runs_by_loadout"][loadout] = {"count": 0, "avg_edit": [], "ratings": []}
        lo_data = insights["runs_by_loadout"][loadout]
        lo_data["count"] += 1
        if sig.get("avg_edit_distance") is not None:
            lo_data["avg_edit"].append(sig["avg_edit_distance"])
        if sig.get("client_rating") is not None:
            lo_data["ratings"].append(sig["client_rating"])

        # Per-skill tracking
        for skill_name, edit_dist in sig.get("edit_distances", {}).items():
            if skill_name not in insights["skill_performance"]:
                insights["skill_performance"][skill_name] = {"runs": 0, "edit_distances": [], "rejections": 0}
            sp = insights["skill_performance"][skill_name]
            sp["runs"] += 1
            sp["edit_distances"].append(edit_dist)
            if edit_dist >= 80:
                sp["rejections"] += 1

    # Compute project health scores
    for proj_name, proj_data in insights["runs_by_project"].items():
        avg_edit = sum(proj_data["avg_edit"]) / len(proj_data["avg_edit"]) if proj_data["avg_edit"] else None
        avg_rating = sum(proj_data["ratings"]) / len(proj_data["ratings"]) if proj_data["ratings"] else None
        insights["project_health"][proj_name] = {
            "runs": proj_data["count"],
            "avg_edit_distance": round(avg_edit, 1) if avg_edit else None,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
        }

    # Check V2 readiness per loadout
    insights["v2_candidates"] = [
        lo for lo, data in insights["runs_by_loadout"].items()
        if data["count"] >= 50
    ]

    # Action items
    items = []
    for skill, sp in insights["skill_performance"].items():
        if sp["runs"] >= 5:
            avg = sum(sp["edit_distances"]) / len(sp["edit_distances"])
            if avg > 60:
                items.append(f"[HIGH] Skill '{skill}' avg edit {avg:.0f}% over {sp['runs']} runs — needs V2 rewrite")
            rej_rate = sp["rejections"] / sp["runs"] * 100
            if rej_rate > 40:
                items.append(f"[HIGH] Skill '{skill}' rejected {rej_rate:.0f}% of the time")

    if insights["v2_candidates"]:
        items.append(f"[INFO] V2 ready for loadouts: {', '.join(insights['v2_candidates'])}")

    insights["action_items"] = items
    insights["last_updated"] = datetime.now(timezone.utc).isoformat()

    GLOBAL_INSIGHTS_FILE.write_text(json.dumps(insights, indent=2))
    return insights


def poll_once() -> list[dict]:
    """Run one global poll cycle."""
    state = _load_state()
    projects = discover_projects()

    if not projects:
        return []

    new_logs = scan_logs(projects, state)
    if not new_logs:
        return []

    results = []
    for log in new_logs:
        try:
            result = process_log(log)
            results.append(result)

            # Mark processed
            proj = log["_project"]
            if proj not in state["processed"]:
                state["processed"][proj] = []
            state["processed"][proj].append(log["_log_id"])
        except Exception as e:
            print(f"  [ERROR] {log['_log_id']}: {e}")
            proj = log["_project"]
            if proj not in state["processed"]:
                state["processed"][proj] = []
            state["processed"][proj].append(log["_log_id"])

    _save_state(state)

    if results:
        update_global_insights(results)

    return results


def sync_projects():
    """Push toolbox state back to all projects."""
    from .sync import sync_all
    try:
        synced = sync_all()
        if synced:
            return synced
    except Exception as e:
        print(f"  [SYNC ERROR] {e}")
    return []


def run_scout():
    """Run scout cycle if API key is available."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        from .scout import scout_cycle
        return scout_cycle(api_key)
    except Exception as e:
        print(f"  [SCOUT ERROR] {e}")
        return None


def poll_loop(interval: int = 60):
    """Continuous global polling loop with sync and scouting."""
    projects = discover_projects()
    has_api_key = bool(os.environ.get("OPENROUTER_API_KEY"))

    print(f"ToolMaster Global Watcher v3")
    print(f"  Monitoring {len(projects)} projects under {CLAUDE_DIR}")
    for p in projects:
        print(f"    • {p['name']}")
    print(f"  Interval: {interval}s")
    print(f"  Sync: every 10 cycles (~5 min)")
    print(f"  Scout: {'every 60 cycles (~30 min)' if has_api_key else 'DISABLED (no OPENROUTER_API_KEY)'}")
    print(f"  State: {GLOBAL_STATE_FILE}")
    print(f"  Insights: {GLOBAL_INSIGHTS_FILE}")
    print(f"  Press Ctrl+C to stop\n")

    # Initial sync on startup
    synced = sync_projects()
    if synced:
        print(f"  [SYNC] Initial sync: {len(synced)} projects updated")

    cycle = 0
    while True:
        cycle += 1
        ts = datetime.now().strftime("%H:%M:%S")

        results = poll_once()
        if results:
            print(f"[{ts}] Cycle {cycle}: {len(results)} new logs")
            for r in results:
                sig = r["signals"]
                print(f"  {r['project']}: edit={sig.get('avg_edit_distance', '?')}% "
                      f"rating={r['rating']}/5 loadout={sig.get('loadout', '?')}")

            # Print action items if any
            insights = json.loads(GLOBAL_INSIGHTS_FILE.read_text()) if GLOBAL_INSIGHTS_FILE.exists() else {}
            for item in insights.get("action_items", []):
                print(f"  ⚡ {item}")

        # Handoff health check every 20 cycles (~10 min at 30s interval)
        if cycle % 20 == 0:
            hh = check_handoff_health()
            if hh["missing"] or hh["stale"]:
                print(f"[{ts}] [HANDOFF] {len(hh['ok'])}/{hh['total']} OK | "
                      f"{len(hh['missing'])} missing | {len(hh['stale'])} stale (>{HANDOFF_STALE_HOURS}h)")

        # Sync every 10 cycles (push digest + enforce CLAUDE.md)
        if cycle % 10 == 0:
            synced = sync_projects()
            if synced:
                print(f"[{ts}] [SYNC] Updated {len(synced)} projects: digest, prompt, CLAUDE.md enforcement")

        # Scout every 60 cycles (~30 min at 30s interval)
        # Ramps up when more data flows in
        if cycle % 60 == 0 and has_api_key:
            print(f"[{ts}] [SCOUT] Starting GitHub scout cycle...")
            scout_result = run_scout()
            if scout_result:
                print(f"[{ts}] [SCOUT] Done: {scout_result.get('skills_found', 0)} skills found, "
                      f"{scout_result.get('proposals_created', 0)} proposals, "
                      f"{scout_result.get('reengineered', 0)} reengineered, "
                      f"{scout_result.get('tokens_used', 0)} tokens")

        elif cycle % 20 == 0 and not results:
            print(f"[{ts}] Cycle {cycle}: listening...")

        time.sleep(interval)


def main():
    import argparse
    parser = argparse.ArgumentParser(prog="toolmaster-watcher", description="ToolMaster global log watcher")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval seconds (default: 60)")
    parser.add_argument("--status", action="store_true", help="Show current insights and exit")
    args = parser.parse_args()

    if args.status:
        if GLOBAL_INSIGHTS_FILE.exists():
            insights = json.loads(GLOBAL_INSIGHTS_FILE.read_text())
            print(f"Total runs: {insights['total_runs']}")
            print(f"\nProject health:")
            for proj, health in insights.get("project_health", {}).items():
                print(f"  {proj}: {health['runs']} runs, edit={health.get('avg_edit_distance', '?')}%, rating={health.get('avg_rating', '?')}/5")
            print(f"\nSkill performance:")
            for skill, sp in insights.get("skill_performance", {}).items():
                avg = sum(sp["edit_distances"]) / len(sp["edit_distances"]) if sp["edit_distances"] else 0
                print(f"  {skill}: {sp['runs']} runs, avg_edit={avg:.0f}%, rejections={sp['rejections']}")
            if insights.get("action_items"):
                print(f"\nAction items:")
                for item in insights["action_items"]:
                    print(f"  {item}")
            if insights.get("v2_candidates"):
                print(f"\nV2 ready: {', '.join(insights['v2_candidates'])}")
            else:
                print(f"\nV2 ready: not yet (need 50 runs per loadout)")
        else:
            print("No insights yet. Run the watcher first.")

        # Always show handoff health in status
        print(f"\nHandoff health:")
        hh = check_handoff_health()
        print(f"  {len(hh['ok'])}/{hh['total']} projects have fresh handoffs")
        if hh["stale"]:
            for s in hh["stale"]:
                print(f"  ⚠ {s['name']}: HANDOFF.md is {s['hours']}h old")
        if hh["missing"]:
            print(f"  ✗ Missing ({len(hh['missing'])}): {', '.join(hh['missing'][:8])}")
            if len(hh["missing"]) > 8:
                print(f"    ... and {len(hh['missing']) - 8} more")
        return

    if args.once:
        results = poll_once()
        print(f"Processed {len(results)} logs" if results else "No new logs")
    else:
        try:
            poll_loop(args.interval)
        except KeyboardInterrupt:
            print("\nWatcher stopped.")


if __name__ == "__main__":
    main()
