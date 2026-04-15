# Discovery Sources Catalog

> Last updated: 2026-04-14
> Source of truth for everywhere ToolMaster's scout can find new skills and candidate repos.

The scout pulls from three tiers of sources. Tier 1 is hardcoded (fast, reliable). Tier 2 is dynamically queried (expands the discovery surface). Tier 3 is manual/future work.

---

## Tier 1: Hardcoded watched repos (`DEFAULT_WATCH_REPOS` in [scout.py](../toolmaster/scout.py))

**Scanned every cycle.** Each run checks these for new `SKILL.md` files via the GitHub tree API.

### Core ecosystem
| Repo | Stars | Notes |
|---|---|---|
| anthropics/skills | 117k | Official Agent Skills spec + reference library |
| obra/superpowers | ~16k | TDD-discipline-driven skill authorship |
| wshobson/agents | 33.6k | Multi-agent orchestration + skill library |
| agentskills/agentskills | 16.2k | Spec + documentation for Agent Skills |
| lobehub/lobe-chat | 60k+ | Workflow-oriented skill frontend |

### High-signal skill libraries (Tier 2 promoted to watched)
| Repo | Stars | Notes |
|---|---|---|
| ComposioHQ/awesome-claude-skills | 53.8k | Curated Claude Skills compilation |
| hesreallyhim/awesome-claude-code | 38.8k | Skills/hooks/commands + meta-index |
| sickn33/antigravity-awesome-skills | 33.1k | 1,400+ installable agentic skills |
| K-Dense-AI/scientific-agent-skills | 18.5k | Research/science/finance skills |
| VoltAgent/awesome-agent-skills | 15.8k | 1,000+ curated agent skills |
| alirezarezvani/claude-skills | 11.1k | 232+ engineering/marketing/compliance |

### Niche/domain-specific
| Repo | Stars | Notes |
|---|---|---|
| OthmanAdi/planning-with-files | 18.7k | Persistent planning skill |
| refly-ai/refly | 7.2k | Open-source skills builder |
| trailofbits/skills | 4.6k | Security research / vulnerability detection |
| heilcheng/awesome-agent-skills | 3.9k | Tutorials + directories |
| softaworks/agent-toolkit | 1.5k | Curated coding agent skills |
| samber/cc-skills-golang | 1.2k | Go-specific skill collection |

### Competitor watch
| Repo | Stars | Why watch |
|---|---|---|
| majiayu000/claude-skill-registry | ~100 | Someone else attempting a skill registry — monitor for convergence |
| addyosmani/agent-skills | 15.5k | Production engineering skill methodology |

---

## Tier 2: Dynamic discovery (new in 2026-04-14 build)

### 2a. GitHub Topics — `_fetch_repos_by_topic()` in [scout.py](../toolmaster/scout.py)

**How it works:** Scout queries `GET /search/repositories?q=topic:<name>+stars:>=50&sort=stars` and takes the top 10 per topic. Rotates through 2 topics per cycle.

Topics currently tracked:
- `agent-skills`
- `claude-code`
- `claude-skills`
- `ai-agents`
- `llm-agent`
- `mcp-server`
- `agent-framework`
- `prompt-engineering`

**Expansion:** add new topics to `GITHUB_TOPICS` in scout.py. No other code changes needed.

### 2b. Awesome-list mining — `_extract_repos_from_awesome_list()` in [scout.py](../toolmaster/scout.py)

**How it works:** Scout fetches an awesome-list repo's `README.md`, regex-extracts `github.com/owner/repo` links, counts mentions (more mentions = more prominent in the list), star-validates the top N against `MIN_DISCOVERY_STARS` (50), and yields the survivors as new repo candidates. Rotates 1 list per cycle.

Lists currently mined:
- `ComposioHQ/awesome-claude-skills`
- `hesreallyhim/awesome-claude-code`
- `VoltAgent/awesome-agent-skills`
- `heilcheng/awesome-agent-skills`
- `e2b-dev/awesome-ai-agents`
- `kaushikb11/awesome-llm-agents`

**Expansion:** add new list repos to `AWESOME_LISTS` in scout.py. The mining logic is recursive-capable — an awesome list of awesome lists will yield all downstream repos, filtered by stars.

### 2c. GitHub code search — (manual, via `gh search code`)

**Not yet wired into scout.** The `gh api search/code?q=filename:SKILL.md` endpoint returns **~160,000 files** as of 2026-04-14. This is the maximum possible discovery surface.

Why not wired yet: GitHub's code search API has stricter rate limits (30 req/min even with auth), and most `SKILL.md` hits are individual project skills, not curated libraries. The star-threshold filter would exclude most results anyway.

**Future wiring:** add a `_search_github_code()` function that queries the code search API, groups results by repo, and promotes repos where `SKILL.md` count ≥ 3 to the watch list.

---

## Tier 3: External sources (not yet wired)

### OSSInsight — https://ossinsight.io

GitHub analytics platform. Tracks 10B+ events. Curates 102+ collections (AI Agent Frameworks, LLM Tools, MCP Client, ai-gateways, etc.).

**Relevance to ToolMaster**: none of the major skill-library repos appear in OSSInsight's "AI Agent Frameworks" collection — the category is pre-aware. When ToolMaster goes public, proposing a new "Agent Skill Libraries" collection is a positioning move worth considering.

**Wiring path**: OSSInsight has a public API at `https://api.ossinsight.io/`. A `_fetch_ossinsight_trending(collection)` function could pull top-N repos from the `llm-tools` and `ai-agent-frameworks` collections as additional candidates. Low priority — GitHub Topics already captures the same signal.

### GitHub Trending — https://github.com/trending

GitHub's native trending list. No public API (scraping only). Worth checking weekly for new AI-related repos that haven't hit the topic tags yet.

### star-history.com

Tracks historical star velocity. Useful for **competitor watch** — see if `anthropics/skills` or any other core watched repo is suddenly accelerating (which would signal a major update or platform push). Not a discovery source.

### libraries.io

Package metadata across 36+ package managers. Relevant for **dependency-based discovery** — if a skill library is published to npm/PyPI, libraries.io can surface it before GitHub does. Not yet wired.

### Hacker News "Show HN" + keyword filter

HN "Show HN" posts for agent/skill projects. Manual for now. Could be automated via the HN API with a keyword filter (`SKILL.md`, `agent skills`, `claude code`).

### Hugging Face Spaces

Some Spaces are agent-skill-like (prompt wrappers, tool configurations). Discovery requires traversing the Hugging Face API. Lower priority.

### Model Context Protocol (MCP) Server Registry

https://github.com/modelcontextprotocol/servers — canonical list of MCP servers. Adjacent to skills (MCP servers expose tools; skills configure their use). Worth mining for skill patterns.

### Twitter/X hashtags

`#claudecode`, `#agentskills`, `#promptengineering`. Manual surveillance for now. Could be automated via nitter scrapes.

### Reddit

`/r/ClaudeAI`, `/r/LocalLLaMA`, `/r/PromptEngineering`. Weekly new-repo announcements. Could be automated via Reddit API.

---

## Rate limits and budget

### GitHub API
- **Unauthenticated**: 60 requests/hour per IP
- **With `GITHUB_TOKEN` or `GH_TOKEN`**: 5,000 requests/hour
- **GitHub Enterprise (if applicable)**: 15,000 requests/hour

Scout reads tokens from env via `_github_headers()`. Set `GITHUB_TOKEN=$(gh auth token)` before launching the watcher for auth'd access.

### Scout cycle budget
- Default: 50,000 tokens per cycle (`budget_tokens` param in `scout_cycle()`)
- Haiku 4.5 via OpenRouter: ~$0.001 per audit call
- Typical cycle: 15-30 audits + 0-5 re-engineer calls = $0.05-0.10 per cycle

### Typical audit distribution (observed 2026-04-14)
- `import`: ~20% (clean, proven skills)
- `extract_techniques`: ~60% (useful but not drop-in safe)
- `reject_unsafe`: ~15% (security concerns flagged)
- `ignore` / `not_relevant`: ~5%

---

## How to add a new source

**For a known high-value repo**: add to `DEFAULT_WATCH_REPOS` in [scout.py](../toolmaster/scout.py). One line.

**For a new GitHub topic**: add to `GITHUB_TOPICS`. Scout will pick it up on the next cycle rotation.

**For a new awesome list**: add to `AWESOME_LISTS`. Must be a GitHub repo with a README.md containing github.com links.

**For a new API source (OSSInsight, libraries.io, etc.)**: write a `_fetch_<source>()` function that returns `list[{full_name, description, stars, updated, source}]`. Call it from `_search_github_repos()` alongside the existing phases.

---

## Observed numbers (2026-04-14)

- **Total `SKILL.md` files on GitHub**: 159,968 (via `gh api search/code`)
- **Total audited this machine**: 342 (from `~/.toolmaster/scout_state.json`)
- **Repos in scout watch list**: 19 (hardcoded)
- **Topics in rotation**: 8
- **Awesome lists in rotation**: 6
- **Typical cycle expansion**: 5-6 → 50+ repos searched per run
