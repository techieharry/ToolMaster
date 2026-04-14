"""Content-addressed skill store.

Skills are hashed by their directory contents (SHA-256).
Each file becomes a blob. A manifest ties them together.
The manifest hash is the skill version identifier.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone


TOOLMASTER_HOME = Path.home() / ".toolmaster"
STORE_DIR = TOOLMASTER_HOME / "store"
BLOBS_DIR = STORE_DIR / "blobs"
MANIFESTS_DIR = STORE_DIR / "manifests"
LOADOUTS_DIR = TOOLMASTER_HOME / "loadouts"
RECORDINGS_DIR = TOOLMASTER_HOME / "recordings"


def ensure_dirs():
    """Create store directories if they don't exist."""
    for d in [BLOBS_DIR, MANIFESTS_DIR, LOADOUTS_DIR, RECORDINGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def hash_bytes(data: bytes) -> str:
    """SHA-256 hash of bytes, returned as hex string."""
    return hashlib.sha256(data).hexdigest()


def store_blob(data: bytes) -> str:
    """Store content-addressed blob. Returns hash."""
    ensure_dirs()
    h = hash_bytes(data)
    blob_path = BLOBS_DIR / h
    if not blob_path.exists():
        blob_path.write_bytes(data)
    return h


def read_blob(h: str) -> bytes:
    """Read blob by hash."""
    blob_path = BLOBS_DIR / h
    if not blob_path.exists():
        raise FileNotFoundError(f"Blob not found: {h}")
    return blob_path.read_bytes()


def pin_skill(skill_dir: str | Path, skip_quality_gate: bool = False) -> dict:
    """Pin a skill directory into the content-addressed store.

    Quality gate: skill must score >= 60 to be pinned.
    Use skip_quality_gate=True only for internal/legacy skills.

    Returns the manifest dict with the manifest hash as 'id'.
    """
    skill_dir = Path(skill_dir).resolve()
    if not skill_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {skill_dir}")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"No SKILL.md found in {skill_dir}")

    # Quality gate (salvaged from Skill Forge)
    if not skip_quality_gate:
        from .quality import validate_and_gate
        passed, report = validate_and_gate(skill_dir)
        if not passed:
            raise ValueError(
                f"Quality gate failed for {skill_dir.name}: "
                f"score {report['score']}/100 (need {report['threshold']}). "
                f"Issues: {report['critical'] + report['high']}"
            )

    # Parse name from SKILL.md frontmatter
    name = _parse_skill_name(skill_md)

    # Walk directory, hash and store each file
    files = {}
    for root, _, filenames in os.walk(skill_dir):
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            filepath = Path(root) / fname
            rel_path = filepath.relative_to(skill_dir).as_posix()
            content = filepath.read_bytes()
            blob_hash = store_blob(content)
            files[rel_path] = {
                "hash": blob_hash,
                "size": len(content),
            }

    # Build manifest
    manifest = {
        "name": name,
        "source": str(skill_dir),
        "pinned_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }

    # Manifest hash = hash of canonical JSON representation
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest_hash = hash_bytes(manifest_bytes)
    manifest["id"] = manifest_hash

    # Store manifest
    ensure_dirs()
    manifest_path = MANIFESTS_DIR / f"{manifest_hash}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    return manifest


def resolve_skill(manifest_hash: str, target_dir: str | Path) -> Path:
    """Resolve a pinned skill to a target directory.

    Reconstructs the skill directory from stored blobs.
    Returns the path to the reconstructed directory.
    """
    manifest_path = MANIFESTS_DIR / f"{manifest_hash}.json"
    if not manifest_path.exists():
        # Try prefix match
        matches = list(MANIFESTS_DIR.glob(f"{manifest_hash}*.json"))
        if len(matches) == 1:
            manifest_path = matches[0]
        elif len(matches) > 1:
            raise ValueError(f"Ambiguous hash prefix '{manifest_hash}' — matches {len(matches)} manifests")
        else:
            raise FileNotFoundError(f"Manifest not found: {manifest_hash}")

    manifest = json.loads(manifest_path.read_text())
    target_dir = Path(target_dir) / manifest["name"]
    target_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, file_info in manifest["files"].items():
        blob_data = read_blob(file_info["hash"])
        out_path = target_dir / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(blob_data)

    return target_dir


def list_skills() -> list[dict]:
    """List all pinned skills in the store."""
    ensure_dirs()
    skills = []
    for mf in sorted(MANIFESTS_DIR.glob("*.json")):
        manifest = json.loads(mf.read_text())
        skills.append({
            "id": manifest["id"],
            "short_id": manifest["id"][:12],
            "name": manifest["name"],
            "pinned_at": manifest["pinned_at"],
            "files": len(manifest["files"]),
            "source": manifest.get("source", "unknown"),
        })
    return skills


def get_manifest(manifest_hash: str) -> dict:
    """Get a manifest by hash or prefix."""
    manifest_path = MANIFESTS_DIR / f"{manifest_hash}.json"
    if not manifest_path.exists():
        matches = list(MANIFESTS_DIR.glob(f"{manifest_hash}*.json"))
        if len(matches) == 1:
            manifest_path = matches[0]
        elif len(matches) > 1:
            raise ValueError(f"Ambiguous hash prefix '{manifest_hash}'")
        else:
            raise FileNotFoundError(f"Manifest not found: {manifest_hash}")
    return json.loads(manifest_path.read_text())


def _parse_skill_name(skill_md: Path) -> str:
    """Parse skill name from SKILL.md YAML frontmatter."""
    content = skill_md.read_text()
    lines = content.split("\n")

    in_frontmatter = False
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break
        if in_frontmatter and stripped.startswith("name:"):
            name = stripped[5:].strip().strip('"').strip("'")
            if name:
                return name

    # Fallback: use parent directory name
    return skill_md.parent.name
