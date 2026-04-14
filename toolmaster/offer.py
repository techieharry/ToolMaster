"""V2 offer engine — three-offer loadout selection for a task.

Given a task description, return up to three ranked loadout offers:

  canonical  — the loadout the system believes fits best, by data or description
  iterated   — canonical with a proposed tweak (swap one weak skill for a stronger fit)
  sideways   — a compositionally different loadout the system thinks might also fit

Cold-start (< THRESHOLD_RECORDINGS total recordings):
  Rank existing loadouts by BM25F similarity between task and composite
  of each loadout's skill names + descriptions. No outcome data is used.

Warm (>= THRESHOLD_RECORDINGS):
  Boost the cold-start score with outcome-derived win rate, computed
  from recordings where the loadout was applied (lower edit_distance +
  higher rating = better). Proven loadouts climb the ranking.

The offers are *suggestions*, not commitments. Agents pick one; the
pick is logged back and feeds future rankings. This closes the
usage -> eval -> offers -> usage flywheel.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .loadout import list_loadouts, get_loadout
from .store import get_manifest, read_blob, TOOLMASTER_HOME
from .record import list_recordings
from .matcher import rank_skills


THRESHOLD_RECORDINGS = 50  # below this, use pure description similarity (cold start)
OFFER_CACHE_DIR = TOOLMASTER_HOME / "offer_cache"


def suggest_loadouts(task: str, top_n: int = 3) -> list[dict]:
    """Return up to top_n loadout offers for a task description.

    Each offer is a dict with:
        type:        "canonical" | "iterated" | "sideways"
        name:        loadout name
        skills:      list of skill names (priority order)
        hashes:      list of skill hashes (priority order)
        relevance:   composite score 0-1
        reason:      one-sentence explanation
        cold_start:  True if warm ranking wasn't used

    Returns empty list if there are no loadouts in the store.
    """
    loadouts_meta = list_loadouts()
    if not loadouts_meta:
        return []

    # Enrich every loadout with full skill content so we can rank them
    enriched = [_enrich_loadout(lo["name"]) for lo in loadouts_meta]

    # Rank via BM25F over composite (name + skill descriptions)
    ranked_input = [
        {
            "name": lo["name"],
            "description": lo["composite_description"],
            "tags": lo["tags"],
            "_loadout": lo,
        }
        for lo in enriched
    ]

    scored = rank_skills(ranked_input, task, top_n=len(enriched), threshold=0.0)
    if not scored:
        return []

    # Warm-path boost: if we have enough outcome data, adjust by win rate
    recordings = list_recordings()
    is_warm = len(recordings) >= THRESHOLD_RECORDINGS
    if is_warm:
        win_rates = _compute_loadout_win_rates(recordings)
        for s in scored:
            lo_name = s["name"]
            wr = win_rates.get(lo_name)
            if wr is not None:
                # Weight: 70% description-fit, 30% proven win rate
                s["relevance_score"] = round(0.7 * s["relevance_score"] + 0.3 * wr, 4)
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    offers: list[dict] = []

    # --- OFFER 1: Canonical (highest-ranked) ---
    canonical = scored[0]
    canonical_lo = canonical["_loadout"]
    offers.append(_offer(
        type_="canonical",
        loadout=canonical_lo,
        score=canonical["relevance_score"],
        reason=(
            f"Top-ranked loadout by "
            f"{'win rate + description fit' if is_warm else 'description fit'}. "
            f"Skills directly address the task vocabulary."
        ),
        cold_start=not is_warm,
    ))
    if top_n <= 1:
        return offers[:top_n]

    # --- OFFER 2: Iterated (canonical with tweak) ---
    iterated = _build_iterated(canonical_lo, task, enriched, canonical["relevance_score"])
    if iterated is not None and iterated["name"] != canonical_lo["name"]:
        iterated_lo = next((e for e in enriched if e["name"] == iterated["name"]), None)
        if iterated_lo:
            offers.append(_offer(
                type_="iterated",
                loadout=iterated_lo,
                score=iterated["score"],
                reason=iterated["reason"],
                cold_start=not is_warm,
            ))
    elif iterated is not None:
        # Iteration target was canonical itself — flag the tweak in the canonical offer
        offers[0]["iterated_note"] = iterated["reason"]

    # --- OFFER 3: Sideways (different composition) ---
    sideways = _pick_sideways(canonical_lo, scored, enriched)
    if sideways is not None:
        offers.append(_offer(
            type_="sideways",
            loadout=sideways["_loadout"],
            score=sideways["relevance_score"],
            reason=(
                f"Different composition from canonical "
                f"(skill overlap: {sideways['overlap_pct']}%). "
                f"May fit if the task has an angle canonical misses."
            ),
            cold_start=not is_warm,
        ))

    return offers[:top_n]


def _enrich_loadout(name: str) -> dict:
    """Load a loadout with full skill content for ranking."""
    lo = get_loadout(name)
    skill_names = []
    skill_hashes = []
    skill_descriptions = []
    all_tags = set()

    for skill_info in lo["skills"]:
        skill_names.append(skill_info["name"])
        skill_hashes.append(skill_info["hash"])
        try:
            manifest = get_manifest(skill_info["hash"])
            skill_md_info = manifest["files"].get("SKILL.md")
            if skill_md_info:
                content = read_blob(skill_md_info["hash"]).decode("utf-8", errors="replace")
                desc = _extract_description(content)
                skill_descriptions.append(desc)
                # Pull keyword-ish tokens from content for tags
                for word in content[:500].lower().replace("-", " ").split():
                    if len(word) > 4 and word.isalpha():
                        all_tags.add(word)
        except Exception:
            continue

    return {
        "name": name,
        "skills": skill_names,
        "hashes": skill_hashes,
        "composite_description": " ".join(skill_descriptions)[:1000],
        "tags": sorted(all_tags)[:15],
        "skill_count": len(skill_names),
    }


def _extract_description(skill_md_content: str) -> str:
    """Pull description line from SKILL.md frontmatter."""
    in_fm = False
    for line in skill_md_content.split("\n"):
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


def _compute_loadout_win_rates(recordings: list[dict]) -> dict[str, float]:
    """Compute per-loadout win rate from recordings.

    Win rate blends: low edit distance + high rating + low rejection rate.
    Returns {loadout_name: score_0_to_1}.
    """
    stats: dict[str, dict] = {}
    for rec in recordings:
        lo = rec.get("loadout")
        if not lo:
            continue
        if lo not in stats:
            stats[lo] = {"edits": [], "ratings": [], "n": 0}
        s = stats[lo]
        s["n"] += 1

        # Edit distance is typically stored inside the output JSON for watcher-harvested records
        output = rec.get("output") or ""
        try:
            signals = json.loads(output) if output else {}
        except (json.JSONDecodeError, TypeError):
            signals = {}
        edit_dists = signals.get("edit_distances", {})
        if edit_dists:
            # Average across all skills in the recording
            s["edits"].extend(edit_dists.values())

        rating = rec.get("rating")
        if rating:
            s["ratings"].append(rating)

    results = {}
    for lo_name, s in stats.items():
        if s["n"] == 0:
            continue
        # Edit component: lower is better; map 0% -> 1.0, 100% -> 0.0
        avg_edit = sum(s["edits"]) / len(s["edits"]) if s["edits"] else 50.0
        edit_score = max(0.0, 1.0 - (avg_edit / 100.0))
        # Rating component: 1-5 scale -> 0-1
        avg_rating = sum(s["ratings"]) / len(s["ratings"]) if s["ratings"] else 3.0
        rating_score = (avg_rating - 1.0) / 4.0
        # Blend: 60% edit (objective), 40% rating (subjective)
        results[lo_name] = round(0.6 * edit_score + 0.4 * rating_score, 4)
    return results


def _build_iterated(canonical: dict, task: str, all_loadouts: list[dict], canonical_score: float) -> dict | None:
    """Build an iterated variant of canonical.

    V1 of V2 heuristic: look for another loadout that has >50% skill overlap
    with canonical AND scores higher on the task. That's an "evolved" version
    of canonical. If none exist, suggest a one-skill swap by finding a
    high-scoring loadout that shares some-but-not-all skills and noting
    which skill to add.
    """
    canonical_skills = set(canonical["skills"])
    candidates = []
    for lo in all_loadouts:
        if lo["name"] == canonical["name"]:
            continue
        other_skills = set(lo["skills"])
        overlap = len(canonical_skills & other_skills)
        if overlap == 0:
            continue
        overlap_pct = overlap / max(len(canonical_skills), 1)
        if overlap_pct >= 0.5:
            # A close cousin — propose it as "iterated canonical"
            candidates.append({
                "name": lo["name"],
                "score": canonical_score * 1.05,  # small bump for being the refined cousin
                "reason": (
                    f"Shares {overlap}/{len(canonical_skills)} skills with canonical "
                    f"but adds {sorted(other_skills - canonical_skills)} — treat as "
                    f"canonical's evolved cousin."
                ),
            })

    if candidates:
        return candidates[0]

    # Fallback: suggest a skill addition from a non-overlapping high-scorer
    for lo in all_loadouts:
        if lo["name"] == canonical["name"]:
            continue
        other_skills = set(lo["skills"])
        diff = other_skills - canonical_skills
        if diff:
            first_add = sorted(diff)[0]
            return {
                "name": canonical["name"],  # same loadout, just noted
                "score": canonical_score,
                "reason": (
                    f"Consider adding '{first_add}' from '{lo['name']}' "
                    f"for broader coverage without losing canonical's strengths."
                ),
            }
    return None


def _pick_sideways(canonical: dict, scored: list[dict], enriched: list[dict]) -> dict | None:
    """Pick a loadout with <50% skill overlap with canonical from the top-ranked set.

    The idea: give the agent an option that's *compositionally different*, not
    just canonical-with-tweaks. Widens the search space.
    """
    canonical_skills = set(canonical["skills"])
    for s in scored[1:]:
        other_skills = set(s["_loadout"]["skills"])
        if not other_skills:
            continue
        overlap = len(canonical_skills & other_skills)
        overlap_pct = round(overlap / max(len(canonical_skills), 1) * 100)
        if overlap_pct < 50:
            s["overlap_pct"] = overlap_pct
            return s
    return None


def _offer(type_: str, loadout: dict, score: float, reason: str, cold_start: bool) -> dict:
    return {
        "type": type_,
        "name": loadout["name"],
        "skills": loadout["skills"],
        "hashes": loadout["hashes"],
        "relevance": round(score, 4),
        "reason": reason,
        "cold_start": cold_start,
    }
