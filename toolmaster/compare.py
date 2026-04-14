"""Loadout comparison — the survival test.

Compares two loadouts by analyzing their skill compositions against
recorded tasks. Uses LLM-as-judge when API key available, falls back
to heuristic scoring.
"""

import hashlib
import json
import os
from pathlib import Path

from .store import get_manifest, read_blob, TOOLMASTER_HOME
from .loadout import get_loadout
from .record import list_recordings


# Cost per 1M tokens for the judge models (rough, public list prices as of 2026)
COST_PER_1M_TOKENS = {
    "anthropic/claude-haiku-4.5":  {"input": 1.00, "output": 5.00},
    "anthropic/claude-haiku-4-5":  {"input": 1.00, "output": 5.00},
    "claude-haiku-4-5-20251001":   {"input": 1.00, "output": 5.00},
    "anthropic/claude-sonnet-4.6": {"input": 3.00, "output": 15.00},
    "default":                     {"input": 1.00, "output": 5.00},
}

COMPARE_CACHE_DIR = TOOLMASTER_HOME / "compare_cache"


def estimate_compare_cost(loadout_a: str, loadout_b: str) -> dict:
    """Estimate token cost before running compare.

    Returns dict with task_count, est_input_tokens, est_output_tokens, est_usd.
    Useful to surface before an LLM-judge run hits the user's API bill.
    """
    try:
        get_loadout(loadout_a)
        get_loadout(loadout_b)
    except FileNotFoundError as e:
        return {"error": str(e)}

    recordings = [r for r in list_recordings() if r.get("status") == "complete"]
    n = len(recordings)
    if n == 0:
        return {"error": "No complete recordings to compare against."}

    # Rough: each judge call sends ~600 input tokens (prompt template + skill previews)
    # and receives ~150 output tokens (JSON verdict). Actual usage varies ±30%.
    est_in = n * 600
    est_out = n * 150
    model = os.environ.get("TOOLMASTER_MODEL", "anthropic/claude-haiku-4.5")
    price = COST_PER_1M_TOKENS.get(model, COST_PER_1M_TOKENS["default"])
    est_usd = (est_in / 1_000_000 * price["input"]) + (est_out / 1_000_000 * price["output"])

    return {
        "task_count": n,
        "est_input_tokens": est_in,
        "est_output_tokens": est_out,
        "est_usd": round(est_usd, 4),
        "model": model,
    }


def _cache_key(loadout_a: str, loadout_b: str, recordings: list[dict]) -> str:
    """Stable cache key: hashes the (loadout pair, recording set) tuple."""
    lo_a = get_loadout(loadout_a)
    lo_b = get_loadout(loadout_b)
    a_hash = "|".join(sorted(s["hash"] for s in lo_a["skills"]))
    b_hash = "|".join(sorted(s["hash"] for s in lo_b["skills"]))
    rec_ids = "|".join(sorted(r["id"] for r in recordings if r.get("status") == "complete"))
    blob = f"{a_hash}::{b_hash}::{rec_ids}".encode()
    return hashlib.sha256(blob).hexdigest()


def _cache_read(key: str) -> dict | None:
    path = COMPARE_CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None
    return None


def _cache_write(key: str, result: dict):
    COMPARE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = COMPARE_CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(result, indent=2))


def compare_loadouts(name_a: str, name_b: str, use_llm: bool = True,
                      use_cache: bool = True) -> dict:
    """Compare two loadouts against all recorded tasks.

    Returns a verdict dict with per-task breakdowns and aggregate scores.
    Results are cached by (loadout_pair, recording_set) hash so a re-run
    against unchanged inputs returns instantly with no LLM cost.
    """
    lo_a = get_loadout(name_a)
    lo_b = get_loadout(name_b)

    # Get skill contents for each loadout
    skills_a = _get_loadout_skills(lo_a)
    skills_b = _get_loadout_skills(lo_b)

    # Get all recordings
    recordings = list_recordings()
    if not recordings:
        return {"error": "No recordings found. Use 'toolmaster record' first."}

    complete = [r for r in recordings if r["status"] == "complete"]
    if not complete:
        return {"error": "No complete recordings. Finish recording some tasks first."}

    # Cache short-circuit: same loadouts + same recordings = same verdict
    cache_key = _cache_key(name_a, name_b, complete)
    if use_cache:
        cached = _cache_read(cache_key)
        if cached is not None:
            cached["from_cache"] = True
            return cached

    # Compare per task — blind A/B with randomized labeling (from Skill Forge)
    import random
    results = []
    for rec in complete:
        # Randomize which loadout is "X" and which is "Y" to eliminate bias
        swap = random.choice([True, False])
        if swap:
            x_skills, y_skills = skills_b, skills_a
            x_name, y_name = name_b, name_a
        else:
            x_skills, y_skills = skills_a, skills_b
            x_name, y_name = name_a, name_b

        if use_llm and _has_api_key():
            verdict = _llm_judge(rec, x_skills, y_skills, "X", "Y")
        else:
            verdict = _heuristic_judge(rec, x_skills, y_skills, "X", "Y")

        # Map blind labels back to real names
        winner_label = verdict["winner"]
        if winner_label == "X":
            verdict["winner"] = x_name
        elif winner_label == "Y":
            verdict["winner"] = y_name
        else:
            verdict["winner"] = "tie"
        verdict["blind_swap"] = swap

        results.append(verdict)

    # Aggregate
    wins_a = sum(1 for r in results if r["winner"] == name_a)
    wins_b = sum(1 for r in results if r["winner"] == name_b)
    ties = sum(1 for r in results if r["winner"] == "tie")

    result = {
        "loadout_a": name_a,
        "loadout_b": name_b,
        "tasks_evaluated": len(results),
        "wins_a": wins_a,
        "wins_b": wins_b,
        "ties": ties,
        "winner": name_a if wins_a > wins_b else name_b if wins_b > wins_a else "tie",
        "method": "llm" if (use_llm and _has_api_key()) else "heuristic",
        "details": results,
        "from_cache": False,
    }
    if use_cache and result["method"] == "llm":
        # Only cache LLM results — heuristic is cheap enough to re-run
        _cache_write(cache_key, result)
    return result


def _get_loadout_skills(loadout: dict) -> list[dict]:
    """Get skill names and SKILL.md content for a loadout."""
    skills = []
    for skill_info in loadout["skills"]:
        manifest = get_manifest(skill_info["hash"])
        # Read SKILL.md content from blob
        skill_md_info = manifest["files"].get("SKILL.md")
        content = ""
        if skill_md_info:
            content = read_blob(skill_md_info["hash"]).decode("utf-8", errors="replace")
            # Truncate to first 2000 chars to save tokens
            if len(content) > 2000:
                content = content[:2000] + "\n... (truncated)"
        skills.append({
            "name": manifest["name"],
            "hash": manifest["id"][:12],
            "content_preview": content,
            "file_count": len(manifest["files"]),
        })
    return skills


def _has_api_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _build_judge_prompt(recording: dict, skills_a: list, skills_b: list,
                        name_a: str, name_b: str) -> str:
    """Build the judge prompt for LLM comparison."""
    skill_desc_a = "\n".join(
        f"  {i+1}. **{s['name']}** ({s['file_count']} files)\n{s['content_preview'][:500]}"
        for i, s in enumerate(skills_a)
    )
    skill_desc_b = "\n".join(
        f"  {i+1}. **{s['name']}** ({s['file_count']} files)\n{s['content_preview'][:500]}"
        for i, s in enumerate(skills_b)
    )

    return f"""You are evaluating two skill loadouts for an AI coding agent. Given a task, determine which loadout would better equip the agent to succeed.

## Task
{recording['task']}

## Task Output (if available)
{recording.get('output', 'N/A')[:1000]}

## Loadout A: "{name_a}" (priority order)
{skill_desc_a}

## Loadout B: "{name_b}" (priority order)
{skill_desc_b}

## Instructions
1. Analyze what capabilities each loadout provides for this specific task
2. Consider: skill relevance, coverage gaps, priority ordering, potential conflicts
3. Pick a winner or declare a tie

Respond in exactly this JSON format:
{{"winner": "{name_a}" or "{name_b}" or "tie", "confidence": 0.0-1.0, "reasoning": "one sentence"}}"""


def _parse_judge_response(text: str) -> dict:
    """Parse JSON from LLM judge response."""
    text = text.strip()
    try:
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError:
        return {"winner": "tie", "confidence": 0.0, "reasoning": f"Parse error: {text[:100]}"}


def _llm_judge(recording: dict, skills_a: list, skills_b: list,
               name_a: str, name_b: str) -> dict:
    """Use LLM as judge via OpenRouter (preferred) or Anthropic direct."""
    import urllib.request

    prompt = _build_judge_prompt(recording, skills_a, skills_b, name_a, name_b)

    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if openrouter_key:
        text, model_used = _call_openrouter(prompt, openrouter_key)
    elif anthropic_key:
        text, model_used = _call_anthropic(prompt, anthropic_key)
    else:
        return _heuristic_judge(recording, skills_a, skills_b, name_a, name_b)

    result = _parse_judge_response(text)

    return {
        "task": recording["task"][:80],
        "recording_id": recording["id"],
        "winner": result.get("winner", "tie"),
        "confidence": result.get("confidence", 0.0),
        "reasoning": result.get("reasoning", ""),
        "model": model_used,
    }


def _call_openrouter(prompt: str, api_key: str) -> tuple[str, str]:
    """Call OpenRouter API. Returns (response_text, model_used)."""
    import urllib.request

    # Use a cheap, fast model for judging
    model = os.environ.get("TOOLMASTER_MODEL", "anthropic/claude-haiku-4.5")

    body = json.dumps({
        "model": model,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/toolmaster",
            "X-Title": "ToolMaster",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"OpenRouter {e.code}: {err_body}") from e

    text = data["choices"][0]["message"]["content"]
    return text, model


def _call_anthropic(prompt: str, api_key: str) -> tuple[str, str]:
    """Call Anthropic API directly. Returns (response_text, model_used)."""
    import urllib.request

    model = "claude-haiku-4-5-20251001"

    body = json.dumps({
        "model": model,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    text = data["content"][0]["text"]
    return text, model


def _heuristic_judge(recording: dict, skills_a: list, skills_b: list,
                     name_a: str, name_b: str) -> dict:
    """Simple heuristic: score by keyword overlap between task and skill names/content."""
    task_words = set(recording["task"].lower().split())

    def score_loadout(skills):
        total = 0
        for s in skills:
            name_words = set(s["name"].replace("-", " ").lower().split())
            content_words = set(s["content_preview"][:500].lower().split())
            # Name match is worth more
            total += len(task_words & name_words) * 3
            total += len(task_words & content_words)
        return total

    score_a = score_loadout(skills_a)
    score_b = score_loadout(skills_b)

    if score_a > score_b:
        winner = name_a
    elif score_b > score_a:
        winner = name_b
    else:
        winner = "tie"

    return {
        "task": recording["task"][:80],
        "recording_id": recording["id"],
        "winner": winner,
        "confidence": 0.5,
        "reasoning": f"Heuristic: keyword overlap scores {name_a}={score_a}, {name_b}={score_b}",
    }
