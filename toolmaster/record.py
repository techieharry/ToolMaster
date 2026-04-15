"""Task recording — capture task sessions for replay-eval."""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from .store import RECORDINGS_DIR, ensure_dirs


def start_recording(task_description: str, loadout_name: str = None, skill_hashes: list[str] = None) -> dict:
    """Start a new recording session.

    Returns the recording dict with an ID.
    """
    ensure_dirs()

    recording = {
        "id": uuid.uuid4().hex[:12],
        "task": task_description,
        "loadout": loadout_name,
        "skill_hashes": skill_hashes or [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "output": None,
        "rating": None,
        "status": "recording",
    }

    _save_recording(recording)
    return recording


def stop_recording(recording_id: str, output: str = None) -> dict:
    """Stop a recording and optionally capture output."""
    recording = get_recording(recording_id)
    recording["ended_at"] = datetime.now(timezone.utc).isoformat()
    recording["output"] = output
    recording["status"] = "complete"
    _save_recording(recording)
    return recording


def rate_recording(recording_id: str, rating: int) -> dict:
    """Rate a recording (1-5)."""
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be 1-5")
    recording = get_recording(recording_id)
    recording["rating"] = rating
    _save_recording(recording)
    return recording


def quick_record(task: str, output: str, loadout_name: str = None,
                 skill_hashes: list[str] = None, rating: int = None) -> dict:
    """Record a complete task in one call (no start/stop ceremony)."""
    ensure_dirs()

    recording = {
        "id": uuid.uuid4().hex[:12],
        "task": task,
        "loadout": loadout_name,
        "skill_hashes": skill_hashes or [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "output": output,
        "rating": rating,
        "status": "complete",
    }

    _save_recording(recording)
    return recording


def get_recording(recording_id: str) -> dict:
    """Get a recording by ID."""
    ensure_dirs()
    rec_path = RECORDINGS_DIR / f"{recording_id}.json"
    if not rec_path.exists():
        raise FileNotFoundError(f"Recording not found: {recording_id}")
    return json.loads(rec_path.read_text(encoding="utf-8", errors="replace"))


def list_recordings(loadout: str = None) -> list[dict]:
    """List all recordings, optionally filtered by loadout."""
    ensure_dirs()
    recordings = []
    for rf in sorted(RECORDINGS_DIR.glob("*.json")):
        rec = json.loads(rf.read_text(encoding="utf-8", errors="replace"))
        if loadout and rec.get("loadout") != loadout:
            continue
        recordings.append(rec)
    return recordings


def _save_recording(recording: dict):
    """Save a recording to disk."""
    rec_path = RECORDINGS_DIR / f"{recording['id']}.json"
    rec_path.write_text(json.dumps(recording, indent=2))
