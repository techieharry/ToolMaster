"""Skill dispatch primitive — delegate a well-scoped task to a specialist agent.

NOT an orchestration framework. This is ToolMaster's minimal-scope answer to
"can a specialist agent with a pinned loadout do this subtask cheaper and
faster than the primary agent doing it inline?"

Shape of the primitive:

    toolmaster delegate "refactor the long handler in foo.py" \\
        --loadout refactor_stack \\
        [--model claude-haiku-4.5] \\
        [--dry-run] \\
        [--no-record]

What it does:
  1. Resolves <loadout> into a system prompt composed of the pinned skills
  2. Calls the specialist model via OpenRouter (or Anthropic direct)
  3. Captures the output
  4. Writes a Recording with loadout, task, output — fuels the flywheel
  5. Returns result text to stdout

What it deliberately does NOT do:
  - Spawn subprocesses or manage concurrency (that's an orchestration framework)
  - Write files to the user's workspace (trust boundary — output is stdout only)
  - Loop, retry, fallback, or plan (one call, one result, by design)
  - Observe its own output or self-correct (the primary agent decides what
    to do with the result)

The trust boundary is critical: ToolMaster is called by the primary agent,
not the other way around. `delegate` is a verb the primary agent uses when
it wants a specialist's opinion or output. The primary stays in control.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .loadout import get_loadout
from .store import get_manifest, read_blob
from .record import quick_record
from .compare import COST_PER_1M_TOKENS


# Token size floors used for cost estimation (rough — actual varies ±30%)
BASE_SYSTEM_TOKENS = 200   # instructions framing the specialist role
TASK_TOKEN_CEILING = 2000  # typical user-task description size
RESPONSE_TOKEN_CEILING = 1500  # typical specialist response


def estimate_delegate_cost(loadout_name: str, task: str, model: str | None = None) -> dict:
    """Estimate token count and USD cost before firing a delegate call.

    Returns dict with loadout, skill_count, est_input_tokens, est_output_tokens,
    est_usd, model. Surfaces on the CLI before the call actually runs so the
    user knows what they're about to spend.
    """
    try:
        lo = get_loadout(loadout_name)
    except FileNotFoundError as e:
        return {"error": str(e)}

    # Approximate skill payload size by summing SKILL.md byte lengths / 4
    skill_tokens = 0
    for skill_info in lo["skills"]:
        try:
            manifest = get_manifest(skill_info["hash"])
            skill_md = manifest["files"].get("SKILL.md")
            if skill_md:
                content = read_blob(skill_md["hash"])
                skill_tokens += len(content) // 4
        except Exception:
            continue

    task_tokens = min(len(task) // 4, TASK_TOKEN_CEILING)
    est_in = BASE_SYSTEM_TOKENS + skill_tokens + task_tokens
    est_out = RESPONSE_TOKEN_CEILING

    model = model or os.environ.get("TOOLMASTER_MODEL", "anthropic/claude-haiku-4.5")
    price = COST_PER_1M_TOKENS.get(model, COST_PER_1M_TOKENS["default"])
    est_usd = (est_in / 1_000_000 * price["input"]) + (est_out / 1_000_000 * price["output"])

    return {
        "loadout": loadout_name,
        "skill_count": len(lo["skills"]),
        "est_input_tokens": est_in,
        "est_output_tokens": est_out,
        "est_usd": round(est_usd, 4),
        "model": model,
    }


def _build_system_prompt(loadout_name: str) -> tuple[str, list[str]]:
    """Build the specialist-agent system prompt from a loadout's skills.

    Returns (system_prompt, list_of_skill_names) — the names are returned
    separately so the recording can log which skills were actually loaded.
    """
    lo = get_loadout(loadout_name)
    skill_contents = []
    skill_names = []

    for skill_info in lo["skills"]:
        try:
            manifest = get_manifest(skill_info["hash"])
            skill_md = manifest["files"].get("SKILL.md")
            if skill_md:
                content = read_blob(skill_md["hash"]).decode("utf-8", errors="replace")
                # Cap each skill at 2000 chars to stay within a sensible budget
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated for delegation)"
                skill_contents.append(f"## Skill: {skill_info['name']}\n\n{content}")
                skill_names.append(skill_info["name"])
        except Exception as e:
            skill_contents.append(f"## Skill: {skill_info['name']}\n\n(failed to load: {e})")
            skill_names.append(skill_info["name"])

    system = (
        f"You are a specialist agent operating with the loadout '{loadout_name}' "
        f"({len(skill_contents)} skills loaded in priority order). "
        f"Complete the task concisely using the skills as guidance. "
        f"Higher-priority skills override lower ones on conflict. "
        f"Return only the task output, no meta-commentary.\n\n"
        + "\n\n---\n\n".join(skill_contents)
    )
    return system, skill_names


def delegate(task: str, loadout_name: str, model: str | None = None,
             dry_run: bool = False, record: bool = True) -> dict:
    """Delegate a task to a specialist agent with a pinned loadout.

    Returns dict: {status, result, model, loadout, skill_names, recording_id, cost_est}
    Raises FileNotFoundError if loadout doesn't exist.
    Returns error dict if no API key is available (does not silently fall back).
    """
    cost_est = estimate_delegate_cost(loadout_name, task, model)
    if "error" in cost_est:
        return {"status": "error", "error": cost_est["error"]}

    if dry_run:
        return {
            "status": "dry_run",
            "result": None,
            "loadout": loadout_name,
            "cost_est": cost_est,
            "message": "Dry run: no API call made. Cost estimate returned for inspection.",
        }

    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "status": "error",
            "error": "No API key. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY before delegating.",
        }

    system_prompt, skill_names = _build_system_prompt(loadout_name)
    model = cost_est["model"]
    is_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))

    try:
        if is_openrouter:
            result_text = _call_openrouter(system_prompt, task, api_key, model)
        else:
            result_text = _call_anthropic(system_prompt, task, api_key)
    except Exception as e:
        return {"status": "error", "error": f"API call failed: {e}"}

    # Write a recording so the dispatched outcome feeds future V2 offer ranking.
    recording_id = None
    if record:
        try:
            rec = quick_record(
                task=f"[delegate] {task}",
                output=result_text,
                loadout_name=loadout_name,
                skill_hashes=[s["hash"] for s in get_loadout(loadout_name)["skills"]],
            )
            recording_id = rec["id"]
        except Exception:
            pass  # Recording failure is non-fatal for the delegate call itself

    return {
        "status": "ok",
        "result": result_text,
        "model": model,
        "loadout": loadout_name,
        "skill_names": skill_names,
        "recording_id": recording_id,
        "cost_est": cost_est,
    }


def _call_openrouter(system: str, user: str, api_key: str, model: str) -> str:
    body = json.dumps({
        "model": model,
        "max_tokens": RESPONSE_TOKEN_CEILING,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/techieharry/ToolMaster",
            "X-Title": "ToolMaster-Delegate",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"OpenRouter {e.code}: {err_body}") from e
    return data["choices"][0]["message"]["content"]


def autopilot(task: str, model: str | None = None, dry_run: bool = False,
              min_relevance: float = 0.05) -> dict:
    """Offer + delegate in one call.

    Runs the V2 offer engine on the task, picks the canonical result if its
    relevance clears `min_relevance`, and delegates to it. Returns the same
    shape as delegate() plus an `offer` field with the chosen offer.

    Fails safe: if no loadout clears the threshold, returns status=no_match
    with the best available offer attached so the caller can decide whether
    to delegate anyway or fall back to inline work.
    """
    from .offer import suggest_loadouts

    offers = suggest_loadouts(task, top_n=3)
    if not offers:
        return {
            "status": "no_loadouts",
            "error": "No loadouts in the store. Create one with 'toolmaster loadout create'.",
        }

    canonical = offers[0]
    if canonical["relevance"] < min_relevance:
        return {
            "status": "no_match",
            "best_offer": canonical,
            "all_offers": offers,
            "message": (
                f"Best offer '{canonical['name']}' scored {canonical['relevance']:.2f}, "
                f"below threshold {min_relevance}. Consider doing inline or passing "
                f"--min-relevance 0 to force delegation."
            ),
        }

    result = delegate(
        task=task,
        loadout_name=canonical["name"],
        model=model,
        dry_run=dry_run,
        record=True,
    )
    result["offer"] = canonical
    result["all_offers"] = offers
    return result


def _call_anthropic(system: str, user: str, api_key: str) -> str:
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": RESPONSE_TOKEN_CEILING,
        "system": system,
        "messages": [{"role": "user", "content": user}],
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"]
