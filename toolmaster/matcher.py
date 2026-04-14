"""BM25F multi-signal skill matcher — ranks skills against task descriptions.

Salvaged from ancrz/skill-swarm-mcp (MIT, 2026).
Adapted: removed rapidfuzz dependency (using stdlib difflib instead),
removed Pydantic/yaml deps, works with ToolMaster's store format.

7 weighted signals:
  exact_match  (30%) — query IS the skill name
  prefix_match (20%) — skill name starts with query or vice versa
  phrase_match (15%) — query found as substring in any field
  bm25f        (15%) — field-weighted BM25F relevance
  jaccard_tags (10%) — Jaccard similarity on tags/keywords
  fuzzy_name   ( 7%) — fuzzy string match on name
  fuzzy_desc   ( 3%) — fuzzy partial match on description
"""

import math
import re
from collections import Counter
from difflib import SequenceMatcher

SIGNAL_WEIGHTS = {
    "exact_match": 30.0,
    "prefix_match": 20.0,
    "phrase_match": 15.0,
    "bm25f": 15.0,
    "jaccard_tags": 10.0,
    "fuzzy_name": 7.0,
    "fuzzy_desc": 3.0,
}
_TOTAL_WEIGHT = sum(SIGNAL_WEIGHTS.values())

_BM25_K1 = 1.2
_BM25_B = 0.3

_FIELD_BOOSTS = {"name": 3.0, "tags": 2.0, "description": 1.0}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _fuzz_ratio(a: str, b: str) -> float:
    """Fuzzy string similarity 0.0-1.0 (stdlib replacement for rapidfuzz)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _fuzz_partial(query: str, text: str) -> float:
    """Best substring match ratio (simplified partial_ratio)."""
    query = query.lower()
    text = text.lower()
    if len(query) >= len(text):
        return SequenceMatcher(None, query, text).ratio()
    best = 0.0
    qlen = len(query)
    for i in range(len(text) - qlen + 1):
        ratio = SequenceMatcher(None, query, text[i:i + qlen]).ratio()
        if ratio > best:
            best = ratio
        if best == 1.0:
            break
    return best


class BM25FIndex:
    """Lightweight BM25F index for a small skill corpus."""

    def __init__(self, skills: list[dict]):
        """skills: list of {name, description, tags (list of str)}"""
        self.skills = skills
        self.N = len(skills)
        self.field_docs = {"name": [], "tags": [], "description": []}
        self.field_avgdl = {}
        self.df = Counter()

        for skill in skills:
            name_tokens = _tokenize(skill.get("name", ""))
            tag_tokens = _tokenize(" ".join(skill.get("tags", [])))
            desc_tokens = _tokenize(skill.get("description", ""))

            self.field_docs["name"].append(name_tokens)
            self.field_docs["tags"].append(tag_tokens)
            self.field_docs["description"].append(desc_tokens)

            all_tokens = set(name_tokens + tag_tokens + desc_tokens)
            for t in all_tokens:
                self.df[t] += 1

        for field in self.field_docs:
            lengths = [len(d) for d in self.field_docs[field]]
            self.field_avgdl[field] = sum(lengths) / max(self.N, 1)

    def score(self, query_tokens: list[str], doc_idx: int) -> float:
        if self.N == 0:
            return 0.0
        total = 0.0
        for term in query_tokens:
            if term not in self.df:
                continue
            df_val = self.df[term]
            idf = math.log(1 + (self.N - df_val + 0.5) / (df_val + 0.5))
            weighted_tf = 0.0
            for field, boost in _FIELD_BOOSTS.items():
                tokens = self.field_docs[field][doc_idx]
                f = tokens.count(term)
                fl = len(tokens)
                avgfl = max(self.field_avgdl[field], 1.0)
                weighted_tf += boost * f / (1 - _BM25_B + _BM25_B * fl / avgfl)
            total += idf * (weighted_tf / (_BM25_K1 + weighted_tf))
        return total


def match_skill(skill: dict, query: str, bm25_index: BM25FIndex = None, doc_idx: int = 0) -> float:
    """Score a single skill against a query. Returns 0.0-1.0."""
    query_lower = query.lower().strip()
    query_tokens = _tokenize(query)
    query_token_set = set(query_tokens)

    if not query_tokens:
        return 0.0

    name_lower = skill.get("name", "").lower()
    tags_lower = [t.lower() for t in skill.get("tags", [])]
    desc_lower = skill.get("description", "").lower()
    combined = f"{name_lower} {' '.join(tags_lower)} {desc_lower}"

    signals = {}

    # Signal 1: Exact match
    signals["exact_match"] = 1.0 if query_lower == name_lower else 0.0

    # Signal 2: Prefix match
    if name_lower.startswith(query_lower):
        signals["prefix_match"] = 1.0
    elif query_lower in name_lower:
        signals["prefix_match"] = 0.7
    elif name_lower in query_lower:
        signals["prefix_match"] = 0.5
    else:
        signals["prefix_match"] = 0.0

    # Signal 3: Phrase match
    signals["phrase_match"] = 1.0 if query_lower in combined else 0.0

    # Signal 4: BM25F
    if bm25_index:
        raw = bm25_index.score(query_tokens, doc_idx)
        signals["bm25f"] = min(raw / 5.0, 1.0)
    else:
        combined_tokens = set(_tokenize(combined))
        overlap = len(query_token_set & combined_tokens)
        signals["bm25f"] = overlap / max(len(query_tokens), 1)

    # Signal 5: Jaccard on tags
    tag_token_set = set(_tokenize(" ".join(tags_lower)))
    intersection = len(query_token_set & tag_token_set)
    union = len(query_token_set | tag_token_set)
    signals["jaccard_tags"] = intersection / union if union > 0 else 0.0

    # Signal 6: Fuzzy name
    signals["fuzzy_name"] = _fuzz_ratio(query_lower, name_lower)

    # Signal 7: Fuzzy description
    signals["fuzzy_desc"] = _fuzz_partial(query_lower, desc_lower) if desc_lower else 0.0

    # Weighted composite
    score = sum(SIGNAL_WEIGHTS[k] * signals[k] for k in SIGNAL_WEIGHTS) / _TOTAL_WEIGHT
    return round(score, 4)


def rank_skills(skills: list[dict], query: str, top_n: int = 10, threshold: float = 0.15) -> list[dict]:
    """Rank all skills against a query. Returns top_n above threshold.

    skills: list of {name, description, tags, ...} dicts
    Returns same dicts with 'relevance_score' added, sorted descending.
    """
    if not skills or not query:
        return []

    bm25 = BM25FIndex(skills)

    scored = []
    for idx, skill in enumerate(skills):
        score = match_skill(skill, query, bm25_index=bm25, doc_idx=idx)
        if score >= threshold:
            skill_copy = dict(skill)
            skill_copy["relevance_score"] = score
            skill_copy["match_method"] = "bm25f"
            scored.append(skill_copy)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored[:top_n]
