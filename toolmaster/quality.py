"""Quality gate — validates skills before they enter the global store.

Adapted from Skill Forge's validate_skill.py (AgriciDaniel/skill-forge).
Every skill must pass this gate before being pinned, harvested, or imported.

Scoring: 0-100 health score
  CRITICAL issue: -20 points
  HIGH issue:     -10 points
  MEDIUM issue:   -5 points
  LOW issue:      -2 points

Pass threshold: 60 (strict: 80)
"""

import re
import json
from pathlib import Path
from typing import Any


def validate_skill(skill_path: str | Path, strict: bool = False) -> dict:
    """Full validation of a skill directory. Returns health report.

    This is the quality gate. Nothing enters the store without passing.
    """
    path = Path(skill_path).resolve()
    issues = []

    # Structure
    issues.extend(_validate_structure(path))

    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        return _report(path, issues, strict)

    content = skill_md.read_text(encoding="utf-8", errors="replace")

    # Frontmatter
    frontmatter, body, parse_errors = _parse_frontmatter(content)
    issues.extend(parse_errors)

    if frontmatter:
        issues.extend(_validate_name(frontmatter.get("name", ""), path.name))
        issues.extend(_validate_description(frontmatter.get("description", "")))

    # Body
    issues.extend(_validate_body(body))

    # Scripts
    issues.extend(_validate_scripts(path))

    # Security (from ToolMaster's scout prescan)
    issues.extend(_validate_security(content))

    return _report(path, issues, strict)


def validate_and_gate(skill_path: str | Path, strict: bool = False) -> tuple[bool, dict]:
    """Validate and return (pass/fail, report). Use as a gate before pinning."""
    report = validate_skill(skill_path, strict)
    return report["status"] == "pass", report


def _report(path: Path, issues: list[str], strict: bool) -> dict:
    score = _calculate_score(issues)
    threshold = 80 if strict else 60
    has_critical = any(i.startswith("CRITICAL:") for i in issues)
    # Any CRITICAL issue = automatic fail regardless of score
    status = "fail" if has_critical else ("pass" if score >= threshold else "fail")

    return {
        "status": status,
        "path": str(path),
        "name": path.name,
        "score": score,
        "threshold": threshold,
        "issues_count": len(issues),
        "critical": [i for i in issues if i.startswith("CRITICAL:")],
        "high": [i for i in issues if i.startswith("HIGH:")],
        "medium": [i for i in issues if i.startswith("MEDIUM:")],
        "low": [i for i in issues if i.startswith("LOW:")],
    }


def _calculate_score(issues: list[str]) -> int:
    score = 100
    for issue in issues:
        if issue.startswith("CRITICAL:"):
            score -= 20
        elif issue.startswith("HIGH:"):
            score -= 10
        elif issue.startswith("MEDIUM:"):
            score -= 5
        elif issue.startswith("LOW:"):
            score -= 2
    return max(0, score)


def _parse_frontmatter(content: str) -> tuple[dict | None, str, list[str]]:
    """Parse YAML frontmatter from SKILL.md."""
    errors = []

    if not content.startswith("---"):
        return None, content, ["CRITICAL: Missing opening '---' delimiter"]

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content, ["CRITICAL: Missing closing '---' delimiter"]

    yaml_text = parts[1].strip()
    body = parts[2].strip()

    if not yaml_text:
        return None, body, ["CRITICAL: Empty frontmatter"]

    frontmatter = {}
    current_key = ""
    current_value = ""
    in_multiline = False

    for line in yaml_text.split("\n"):
        stripped = line.strip()

        if in_multiline:
            if stripped and not re.match(r"^[a-z_-]+:", stripped):
                current_value += " " + stripped
                continue
            else:
                frontmatter[current_key] = current_value.strip()
                in_multiline = False

        match = re.match(r"^([a-z_-]+):\s*(.*)", stripped)
        if match:
            current_key = match.group(1)
            value = match.group(2).strip()
            if value in (">", "|"):
                in_multiline = True
                current_value = ""
            else:
                frontmatter[current_key] = value.strip('"').strip("'")

    if in_multiline:
        frontmatter[current_key] = current_value.strip()

    return frontmatter, body, errors


def _validate_structure(path: Path) -> list[str]:
    issues = []

    if not path.is_dir():
        issues.append(f"CRITICAL: Not a directory: {path}")
        return issues

    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        # Check case variations
        for f in path.iterdir():
            if f.name.lower() == "skill.md" and f.name != "SKILL.md":
                issues.append(f"CRITICAL: Found '{f.name}' but must be exactly 'SKILL.md'")
                return issues
        issues.append("CRITICAL: SKILL.md not found")
        return issues

    folder_name = path.name
    if not re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", folder_name):
        issues.append(f"MEDIUM: Folder name '{folder_name}' is not kebab-case")

    return issues


def _validate_name(name: str, folder_name: str) -> list[str]:
    issues = []

    if not name:
        issues.append("CRITICAL: 'name' field is missing")
        return issues

    if len(name) > 64:
        issues.append(f"CRITICAL: Name too long ({len(name)} chars, max 64)")

    if not re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", name):
        issues.append(f"HIGH: Name '{name}' is not valid kebab-case")

    if name != folder_name:
        issues.append(f"LOW: Name '{name}' does not match folder name '{folder_name}'")

    return issues


def _validate_description(description: str) -> list[str]:
    issues = []

    if not description:
        issues.append("CRITICAL: 'description' field is missing")
        return issues

    if len(description) > 1024:
        issues.append(f"HIGH: Description too long ({len(description)} chars, max 1024)")

    if len(description) < 20:
        issues.append("HIGH: Description too short to explain capabilities")

    if "<" in description or ">" in description:
        issues.append("MEDIUM: Description contains XML angle brackets")

    # Check for trigger phrases
    trigger_patterns = [r"[Uu]se when", r"[Uu]se for", r"[Ww]hen .* says", r"[Tt]rigger"]
    has_trigger = any(re.search(p, description) for p in trigger_patterns)
    if not has_trigger:
        issues.append("MEDIUM: Description missing trigger phrases ('Use when...')")

    return issues


def _validate_body(body: str) -> list[str]:
    issues = []

    lines = body.split("\n")
    line_count = len(lines)

    if line_count > 500:
        issues.append(f"MEDIUM: Body is {line_count} lines (recommend <500)")

    if line_count < 5:
        issues.append("HIGH: Body too short (<5 lines)")

    # Token estimate
    est_tokens = len(body) // 4
    if est_tokens > 5000:
        issues.append(f"MEDIUM: Estimated ~{est_tokens} tokens (recommend <5000)")

    headings = [l for l in lines if l.startswith("#")]
    if len(headings) < 2:
        issues.append("LOW: Few headings — use ## sections for organization")

    return issues


def _validate_scripts(path: Path) -> list[str]:
    issues = []
    scripts_dir = path / "scripts"

    if not scripts_dir.exists():
        return issues

    for script in scripts_dir.glob("*.py"):
        content = script.read_text(encoding="utf-8", errors="replace")
        if '"""' not in content and "'''" not in content:
            issues.append(f"LOW: Script {script.name} missing docstring")

    return issues


def _validate_security(content: str) -> list[str]:
    """Security validation — catches dangerous patterns in skill content."""
    issues = []
    content_lower = content.lower()

    # Prompt injection
    injection_patterns = [
        ("ignore previous", "Prompt injection pattern: 'ignore previous'"),
        ("ignore all prior", "Prompt injection pattern: 'ignore all prior'"),
        ("you are now", "Role override pattern: 'you are now'"),
        ("new instructions:", "Prompt injection: 'new instructions'"),
    ]

    # Data exfiltration
    exfil_patterns = [
        ("curl ", "External command: curl"),
        ("wget ", "External command: wget"),
        ("ngrok", "Tunneling: ngrok reference"),
    ]

    # Dangerous execution
    danger_patterns = [
        ("eval(", "Code execution: eval()"),
        ("exec(", "Code execution: exec()"),
        ("rm -rf", "Destructive command: rm -rf"),
        ("sudo ", "Privilege escalation: sudo"),
    ]

    for patterns, severity_prefix in [
        (injection_patterns, "CRITICAL"),
        (exfil_patterns, "HIGH"),
        (danger_patterns, "HIGH"),
    ]:
        for pattern, desc in patterns:
            if pattern in content_lower:
                issues.append(f"{severity_prefix}: Security — {desc}")

    return issues
