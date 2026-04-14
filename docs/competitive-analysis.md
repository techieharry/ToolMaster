# Competitive Analysis — ToolMaster

## Status: Complete (2026-04-11)

## Four-Primitive Matrix

| Competitor | Immutable Parts | Slot Grammar | Roguelike Offers | Replay-Eval Gate |
|---|---|---|---|---|
| Multica | No. Mutable CRUD, no versioning, no content-addressing. Import lockfile has SHA-256 hashes but stored skills are freely editable. | No. SKILL.md + JSONB config, no enforced schema. | No. Fully manual browse + explicit assignment per agent. | No. Task results tracked but not fed back into skill evaluation. |
| LobeHub | No. Mutable CRUD. ZIP imports have content-hash dedup but skills are editable. | No. Schema-driven manifests (name, desc, version) but no slot constraints on skill body. | No. Manual catalog browsing + import. No auto-select or recommendation. | Partial. Eval system exists (benchmarks + runs + test cases) but standalone QA — not linked to skill promotion. |
| Superpowers (obra) | No. Mutable files on disk, git-versioned. Workflow state is forward-only via hard gates. | No. SKILL.md with YAML frontmatter, flat namespace. No slot system. | No. Context-triggered activation via description matching. No offer mechanic. | Partial. TDD-style pressure testing required for skill authorship (red/green/refactor with subagents). Social/PR process, not automated runtime gate. |
| wshobson/agents | No. Plain files in git. Plugin-level versioning only. | No. SKILL.md with YAML frontmatter (name + description). No slot constraints. | No. Auto-triggered via description matching. No recommendation engine. | Yes (closest). PluginEval: 3-layer system — static analysis, LLM judge (F1 scoring), Monte Carlo simulation (50-100 runs). Quality badges Bronze→Platinum. CI gate mode. |
| Anthropic Agent Skills | No. Stateless instruction packages. No state management at all. | No. YAML frontmatter (name, description, license, compatibility, metadata, allowed-tools). Body is freeform markdown. | No. Model-driven activation via description matching or user slash commands. | No. Validation of frontmatter/naming only. "Monitor and iterate" is the guidance. |

## Correction: "Composio Superpowers"

"Composio Superpowers" was a misnomer in the original concept doc. **Superpowers** is `obra/superpowers` by Jesse Vincent — an independent open-source project. Composio (composio.dev) is a separate platform focused on SaaS integrations/OAuth for AI agents. Composio's blog references Superpowers but they are distinct projects.

## Correction: LobeHub "Self-Evolution Engine"

Does not exist as described. The real system is a **5-layer memory extraction pipeline** (gatekeeper + activity/identity/context/preference/experience extractors) that builds structured user memory over time. Experiences have confidence/value scores but are not used to evolve skills. Marketing copy overstates the mechanism.

## Per-Competitor Detail

### Multica
- **Structure**: SKILL.md + supporting files per directory. Injected into provider-native paths at runtime (Claude, Codex, OpenCode).
- **Selection**: Workspace-scoped catalog. Manual assignment via `SetAgentSkills`. Import from ClawHub marketplace or GitHub.
- **Sharing**: Workspace-scoped. No cross-workspace sharing. External distribution via ClawHub/GitHub.
- **Repo**: `multica-ai/multica` (TS + Go, 6.5k stars, Apache 2.0)

### LobeHub
- **Structure**: Three parallel systems — legacy plugins (manifest + API endpoints + UI), new skills (manifest + content + resource tree), OAuth-connected tools (MCP-compatible).
- **Selection**: Manual browse from builtin/market/user sources. Agent calls `runSkill` at runtime.
- **Memory**: 5-layer extraction (activity, identity, context, preference, experience). Gatekeeper decides extraction per layer. Experiences scored on confidence/knowledge-value/problem-solving.
- **Eval**: Full benchmark system (datasets, test cases, runs) but not wired to skill lifecycle.

### Superpowers (obra/superpowers)
- **Structure**: SKILL.md directories under `skills/`. Flat namespace, no nesting.
- **Flow**: Brainstorm (clarify + spec) → Plan (task decomposition) → Execute (subagent dispatch + TDD) → Finish (review + merge). Hard gates between phases.
- **Composition**: Implicit via textual cross-references between skills. Priority ordering when multiple skills apply. No formal dependency graph.
- **Eval**: Skills require pressure testing (run without skill → document failure → add skill → verify compliance → find loopholes → plug them). PR process, not automated.

### wshobson/agents
- **Structure**: Monolithic SKILL.md per skill directory within plugins. 3-tier progressive disclosure (metadata → instructions → resources).
- **Selection**: Auto-triggered via frontmatter description matching. Plugin installation is manual.
- **Composition**: Implicit via plugin bundling + 16 workflow orchestrators. No skill-to-skill dependency declarations.
- **Eval (PluginEval)**: Layer 1 static (structural analysis, anti-pattern detection). Layer 2 LLM judge (synthetic prompts, F1 triggering accuracy). Layer 3 Monte Carlo (50-100 runs, Wilson/bootstrap/Clopper-Pearson CI). Quality badges. CI gate with `--threshold`. Elo ranking across corpus.
- **Repo**: `wshobson/agents` (77 plugins, 182 agents, 149 skills, 96 commands, 16 orchestrators, MIT)

### Anthropic Agent Skills
- **Structure**: Directory with SKILL.md (YAML frontmatter + markdown body) + optional scripts/references/assets. Progressive disclosure: catalog (~50-100 tokens) → instructions (<5000 tokens) → resources (on demand).
- **Selection**: Model-driven (description matching at startup) or user-explicit (slash commands). Discovery via filesystem scanning (.agents/skills/, .<client>/skills/).
- **Sharing**: Git repos. No registry or package manager in the spec. Claude Code has plugin marketplace for distribution.
- **Spec**: agentskills.io (15.7k stars). Supported by Claude Code, Cursor, VS Code/Copilot, Gemini CLI, OpenAI Codex, JetBrains Junie, Roo Code, Goose, OpenHands, 30+ agents.

## Verdict

**The wedge holds.** No competitor combines all four primitives. Here's the breakdown:

| Primitive | Exists anywhere? | Load-bearing? |
|---|---|---|
| Immutable content-addressed parts | **No.** Everyone is mutable CRUD + git. Multica has import hashes but that's a lockfile, not a paradigm. | **Yes — most differentiated.** This is the foundation. Cache benefits, reproducibility, and audit trail all flow from this. Without it, the other three primitives lose their force multiplier. |
| Five-slot grammar | **No.** Everyone uses freeform markdown with minimal frontmatter. No one constrains skill body structure. | **Medium.** Creative forcing function, but also the highest-risk primitive — could fight markdown's nature. Needs stress testing against real skills before committing. |
| Roguelike three-offer selection | **No.** Everyone is either manual assignment or auto-trigger via description matching. Zero recommendation/offer mechanics anywhere. | **Yes — most novel UX.** This is the emotional hook and the training data flywheel. Nobody is even adjacent to this. |
| Replay-eval promotion gate | **Partial.** wshobson/agents has PluginEval (strong). Superpowers has TDD pressure testing. LobeHub has eval but disconnected from skills. | **Medium.** Needed but not unique enough alone. wshobson's PluginEval is already solid. ToolMaster's version needs to be tightly coupled to the immutable parts + offer system to differentiate. |

### Which primitives are decoration?

None are pure decoration, but the **five-slot grammar is the riskiest** — it's an opinionated schema on top of an ecosystem that has standardized on freeform markdown. It needs to prove it helps composition rather than fighting the format. The other three reinforce each other.

### Biggest threat

Anthropic's roadmap for org-wide skill distribution. If they add a recommendation engine or composition layer to the Agent Skills spec, it could eat ToolMaster's selection and composition advantages. The immutable content-addressed paradigm is the hardest for them to retrofit because it's an architectural choice, not a feature.
