"""Trust scoring engine — evaluates external repos before importing skills.

Salvaged from ancrz/skill-swarm-mcp (MIT, 2026).
Adapted: async→sync, httpx→urllib, removed Pydantic dependency.

5 dimensions:
  Recency     (20%) — exponential decay, half-life 180 days
  Popularity  (20%) — log-normalized stars/forks/watchers
  Maintenance (25%) — push recency + issue count
  Security    (25%) — license trust + archive status
  Completeness(10%) — description, homepage, topics

Verdicts: TRUST (>=0.75), CAUTION (>=0.50), WARNING (>=0.25), REJECT (<0.25)
"""

import json
import math
import urllib.request
from datetime import datetime, timezone

LICENSE_TRUST = {
    "MIT": 1.0, "Apache-2.0": 1.0, "BSD-2-Clause": 1.0, "BSD-3-Clause": 1.0,
    "ISC": 1.0, "0BSD": 1.0, "Unlicense": 0.9, "MPL-2.0": 0.85,
    "LGPL-2.1": 0.7, "LGPL-3.0": 0.7, "GPL-2.0": 0.5, "GPL-3.0": 0.5,
    "AGPL-3.0": 0.4,
}

WEIGHTS = {
    "recency": 0.20,
    "popularity": 0.20,
    "maintenance": 0.25,
    "security": 0.25,
    "completeness": 0.10,
}


def _log_norm(value: int, midpoint: int) -> float:
    if value <= 0:
        return 0.0
    return min(math.log10(1 + value) / math.log10(1 + midpoint), 1.0)


def _days_since(iso_date: str) -> int:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        return 999


def score_recency(pushed_at: str, created_at: str) -> float:
    days = _days_since(pushed_at)
    decay = math.exp(-0.00385 * days)  # half-life 180 days
    age_days = _days_since(created_at)
    age_bonus = min(age_days / 365.0, 1.0) * 0.1
    return min(decay + age_bonus, 1.0)


def score_popularity(stars: int, forks: int, watchers: int) -> float:
    return _log_norm(stars, 10000) * 0.55 + _log_norm(forks, 2000) * 0.30 + _log_norm(watchers, 500) * 0.15


def score_maintenance(open_issues: int, pushed_at: str, archived: bool) -> float:
    if archived:
        return 0.05
    days = _days_since(pushed_at)
    recency = math.exp(-0.0077 * days)  # half-life 90 days
    if open_issues == 0:
        issue_signal = 0.5
    elif open_issues < 20:
        issue_signal = 0.8
    elif open_issues < 100:
        issue_signal = 0.5
    else:
        issue_signal = 0.3
    return recency * 0.6 + issue_signal * 0.4


def score_security(license_spdx: str | None, archived: bool) -> float:
    s_license = LICENSE_TRUST.get(license_spdx, 0.3) if license_spdx else 0.1
    s_archived = 0.0 if archived else 1.0
    return s_license * 0.6 + s_archived * 0.4


def score_completeness(has_description: bool, has_homepage: bool, has_topics: bool) -> float:
    return (1.0 if has_description else 0.0) * 0.4 + \
           (1.0 if has_homepage else 0.0) * 0.3 + \
           (1.0 if has_topics else 0.0) * 0.3


def compute_trust(dimensions: dict[str, float]) -> dict:
    available = sum(1 for v in dimensions.values() if v >= 0)
    confidence = available / len(WEIGHTS)
    total = sum(dimensions.get(k, 0.0) * w for k, w in WEIGHTS.items())
    effective = total * confidence

    if effective >= 0.75:
        verdict = "TRUST"
    elif effective >= 0.50:
        verdict = "CAUTION"
    elif effective >= 0.25:
        verdict = "WARNING"
    else:
        verdict = "REJECT"

    return {
        "score": round(total, 3),
        "confidence": round(confidence, 2),
        "verdict": verdict,
        "dimensions": {k: round(v, 3) for k, v in dimensions.items()},
    }


def evaluate_repo(repo_name: str) -> dict:
    """Evaluate trust score for a GitHub repo (owner/repo format).

    Single API call to /repos/{owner}/{repo}. No auth = 60 req/hr.
    """
    try:
        url = f"https://api.github.com/repos/{repo_name}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ToolMaster-Trust",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        dims = {
            "recency": score_recency(
                data.get("pushed_at", ""),
                data.get("created_at", ""),
            ),
            "popularity": score_popularity(
                data.get("stargazers_count", 0),
                data.get("forks_count", 0),
                data.get("subscribers_count", 0),
            ),
            "maintenance": score_maintenance(
                data.get("open_issues_count", 0),
                data.get("pushed_at", ""),
                data.get("archived", False),
            ),
            "security": score_security(
                data.get("license", {}).get("spdx_id") if data.get("license") else None,
                data.get("archived", False),
            ),
            "completeness": score_completeness(
                bool(data.get("description")),
                bool(data.get("homepage")),
                len(data.get("topics", [])) > 0,
            ),
        }

        return compute_trust(dims)

    except Exception as e:
        return {"score": 0.0, "confidence": 0.0, "verdict": "UNKNOWN", "error": str(e)}
