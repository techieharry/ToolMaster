"""Skill suggestion engine — recommends skills from the global store based on task description.

This is the cross-pollination layer. When an agent in Project B faces a task,
it asks ToolMaster "what's already been built and proven?" instead of generating
from scratch. Saves tokens, improves quality, compounds knowledge across projects.
"""

import json
import os
from pathlib import Path

from .store import list_skills, get_manifest, read_blob, TOOLMASTER_HOME
from .record import list_recordings


def suggest(task_description: str, top_n: int = 5, use_llm: bool = True) -> list[dict]:
    """Suggest skills from the global store that match a task description.

    Returns ranked list of skills with relevance scores and performance data.
    """
    all_skills = list_skills()
    if not all_skills:
        return []

    # Enrich skills with content + performance data
    enriched = []
    recordings = list_recordings()
    performance = _build_performance_index(recordings)

    for skill in all_skills:
        manifest = get_manifest(skill["id"])
        skill_md = manifest["files"].get("SKILL.md")
        content = ""
        if skill_md:
            content = read_blob(skill_md["hash"]).decode("utf-8", errors="replace")

        # Get frontmatter description
        description = _extract_description(content)

        perf = performance.get(skill["name"], {})

        enriched.append({
            "name": skill["name"],
            "hash": skill["id"],
            "short_hash": skill["id"][:12],
            "source": skill.get("source", "unknown"),
            "file_count": skill["files"],
            "description": description,
            "content_preview": content[:500],
            "performance": {
                "times_used": perf.get("times_used", 0),
                "avg_edit_distance": perf.get("avg_edit_distance"),
                "avg_rating": perf.get("avg_rating"),
                "rejection_rate": perf.get("rejection_rate"),
                "projects_used_in": perf.get("projects", []),
            },
        })

    if use_llm and _has_api_key():
        return _llm_rank(task_description, enriched, top_n)
    else:
        return _heuristic_rank(task_description, enriched, top_n)


def suggest_for_project(project_name: str, top_n: int = 10) -> list[dict]:
    """Suggest skills that could benefit a specific project based on its history.

    Looks at what the project has been doing (from recordings) and finds
    proven skills from other projects that address similar tasks.
    """
    recordings = list_recordings()

    # Find this project's tasks
    project_tasks = [
        r["task"] for r in recordings
        if project_name.lower() in r["task"].lower()
    ]

    if not project_tasks:
        return []

    # Combine recent tasks into a profile
    task_profile = " ".join(project_tasks[-10:])
    return suggest(task_profile, top_n=top_n, use_llm=False)


def get_proven_skills(min_uses: int = 3, max_edit_distance: float = 30.0) -> list[dict]:
    """Get skills that are proven across projects — used multiple times with low edit distance.

    These are the "tools that work." The gold standard for cross-project sharing.
    """
    recordings = list_recordings()
    performance = _build_performance_index(recordings)
    all_skills = list_skills()

    proven = []
    for skill in all_skills:
        perf = performance.get(skill["name"], {})
        times_used = perf.get("times_used", 0)
        avg_edit = perf.get("avg_edit_distance")

        if times_used >= min_uses and avg_edit is not None and avg_edit <= max_edit_distance:
            proven.append({
                "name": skill["name"],
                "hash": skill["id"][:12],
                "times_used": times_used,
                "avg_edit_distance": avg_edit,
                "avg_rating": perf.get("avg_rating"),
                "projects": perf.get("projects", []),
            })

    return sorted(proven, key=lambda x: (x["avg_edit_distance"], -x["times_used"]))


def _build_performance_index(recordings: list[dict]) -> dict:
    """Build a performance index from all recordings.

    Returns {skill_name: {times_used, avg_edit_distance, avg_rating, projects}}.
    """
    index = {}

    for rec in recordings:
        task = rec.get("task", "")
        output = rec.get("output", "")

        # Try to parse output as JSON (signals from logger)
        try:
            signals = json.loads(output) if output else {}
        except (json.JSONDecodeError, TypeError):
            signals = {}

        # Extract project name from task (format: [project][type] ...)
        project = "unknown"
        if task.startswith("["):
            bracket_end = task.find("]")
            if bracket_end > 0:
                project = task[1:bracket_end]

        # Track per-skill from edit distances in signals
        for skill_name, edit_dist in signals.get("edit_distances", {}).items():
            if skill_name not in index:
                index[skill_name] = {
                    "times_used": 0,
                    "edit_distances": [],
                    "ratings": [],
                    "projects": set(),
                }
            idx = index[skill_name]
            idx["times_used"] += 1
            idx["edit_distances"].append(edit_dist)
            idx["projects"].add(project)

        # Also track from loadout name if available
        loadout = rec.get("loadout")
        rating = rec.get("rating")
        if rating and loadout:
            # Associate rating with skills in this loadout
            # (rough heuristic — the rating applies to the whole loadout)
            pass

    # Compute averages
    for name, data in index.items():
        if data["edit_distances"]:
            data["avg_edit_distance"] = round(
                sum(data["edit_distances"]) / len(data["edit_distances"]), 1
            )
        else:
            data["avg_edit_distance"] = None

        if data["ratings"]:
            data["avg_rating"] = round(
                sum(data["ratings"]) / len(data["ratings"]), 1
            )
        else:
            data["avg_rating"] = None

        rejections = sum(1 for e in data["edit_distances"] if e >= 80)
        data["rejection_rate"] = round(rejections / len(data["edit_distances"]) * 100, 1) if data["edit_distances"] else None
        data["projects"] = sorted(data["projects"])
        del data["edit_distances"]
        del data["ratings"]

    return index


def _extract_description(content: str) -> str:
    """Extract description from SKILL.md frontmatter."""
    lines = content.split("\n")
    in_fm = False
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                break
        if in_fm and stripped.startswith("description:"):
            return stripped[12:].strip().strip('"').strip("'")
    return ""


def _has_api_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _heuristic_rank(task: str, skills: list[dict], top_n: int) -> list[dict]:
    """Rank skills using BM25F multi-signal matching + performance boost.

    Upgraded from simple keyword overlap to 7-signal composite scoring
    (salvaged from ancrz/skill-swarm-mcp).
    """
    from .matcher import rank_skills as bm25_rank

    # Prepare skills for BM25F matcher (needs name, description, tags)
    matcher_input = []
    for skill in skills:
        # Extract keywords from content as pseudo-tags
        content_words = skill.get("content_preview", "")[:300].lower().split()
        tags = [w for w in content_words if len(w) > 4][:10]
        matcher_input.append({
            "name": skill["name"],
            "description": skill["description"],
            "tags": tags,
            "_original": skill,  # preserve full skill data
        })

    # BM25F ranking
    ranked = bm25_rank(matcher_input, task, top_n=len(skills), threshold=0.05)

    # Map back to original skills and boost by performance
    result = []
    for r in ranked:
        original = r["_original"]
        base_score = r["relevance_score"]

        # Performance boost
        perf = original["performance"]
        perf_boost = 0.0
        if perf["times_used"] > 0:
            perf_boost += min(perf["times_used"] / 20.0, 0.15)  # Up to +0.15
        if perf["avg_edit_distance"] is not None and perf["avg_edit_distance"] < 30:
            perf_boost += 0.10
        if perf["avg_rating"] and perf["avg_rating"] >= 4:
            perf_boost += 0.05

        original["relevance_score"] = round(base_score + perf_boost, 4)
        original["match_method"] = "bm25f"
        result.append(original)

    result.sort(key=lambda x: x["relevance_score"], reverse=True)
    return result[:top_n]


def _llm_rank(task: str, skills: list[dict], top_n: int) -> list[dict]:
    """Use LLM to rank skill relevance for a task."""
    import urllib.request

    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _heuristic_rank(task, skills, top_n)

    skill_list = "\n".join(
        f"{i+1}. **{s['name']}** — {s['description'][:200]} "
        f"(used {s['performance']['times_used']}x, "
        f"edit={s['performance']['avg_edit_distance'] or '?'}%)"
        for i, s in enumerate(skills[:20])  # Cap at 20 to save tokens
    )

    prompt = f"""Given this task, rank which skills are most relevant. Return a JSON array of skill names in order of relevance, most relevant first.

Task: {task}

Available skills:
{skill_list}

Return ONLY a JSON array of skill names, e.g.: ["skill-a", "skill-b", "skill-c"]
Top {top_n} most relevant only. If fewer than {top_n} are relevant, return fewer."""

    model = os.environ.get("TOOLMASTER_MODEL", "anthropic/claude-haiku-4.5")
    is_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))

    if is_openrouter:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/toolmaster",
            "X-Title": "ToolMaster",
        }
        body = json.dumps({
            "model": model,
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
    else:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        if is_openrouter:
            text = data["choices"][0]["message"]["content"]
        else:
            text = data["content"][0]["text"]

        # Parse the ranked names
        text = text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        ranked_names = json.loads(text)

        # Map back to skill objects
        name_to_skill = {s["name"]: s for s in skills}
        result = []
        for i, name in enumerate(ranked_names):
            if name in name_to_skill:
                skill = name_to_skill[name]
                skill["relevance_score"] = len(ranked_names) - i
                skill["match_method"] = "llm"
                result.append(skill)

        return result[:top_n]

    except Exception as e:
        # Fallback to heuristic
        return _heuristic_rank(task, skills, top_n)
