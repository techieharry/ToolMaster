# Background Jobs (V3)

## Status: Designed, not built. Gated on V2 offer engine proving value.

Decomposed from the original "toolbox master" concept. Each job is independent with its own trigger, model tier, and token budget.

## Jobs

### 1. Dedup Job
- **What**: Scan store for semantically duplicate skills (different words, same behavior)
- **How**: Embed skill descriptions + first 500 tokens of body → cosine similarity → flag pairs above threshold
- **Model**: Embedding model (e.g., voyage-3) for similarity, Haiku for confirmation
- **Trigger**: Weekly, or on `toolmaster dedup` command
- **Output**: List of candidate merges for human review. Never auto-merges.
- **Budget**: ~10k tokens per scan of 100 skills

### 2. Scout Job
- **What**: Scan configured external repos for skills that fill gaps in existing loadouts
- **How**: Fetch repo skill directories → compare against store → flag novel skills
- **Model**: Haiku for relevance assessment
- **Trigger**: On `toolmaster scout` command, or weekly against watched repos
- **Output**: List of candidate skills to pin, with relevance reasoning
- **Budget**: ~5k tokens per repo scanned
- **Safety**: Read-only. Never auto-imports. Human reviews and pins manually.

### 3. Iterate Job
- **What**: Fork existing skills, mutate instructions, eval against replay logs
- **How**: Take a skill → generate N variants (instruction tweaks) → replay-eval each → surface best as offer candidate
- **Model**: Sonnet for mutation, Haiku for eval judging
- **Trigger**: On `toolmaster iterate <skill-hash>` command
- **Output**: New pinned skill variants with eval scores vs original
- **Budget**: ~50k tokens per iteration cycle (configurable)

## Design principles

- Every job is a CLI command first, scheduled job second
- All output is suggestions for human review, never autonomous action
- Token budgets are shown before execution and configurable
- Dry-run mode (`--dry-run`) on every job
