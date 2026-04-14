# Five-Slot Grammar — KILLED

**Status**: Killed 2026-04-11 during stress test.

**Reason**: The entire ecosystem (Anthropic spec, wshobson, Superpowers, Multica, LobeHub) has standardized on freeform markdown. The spec explicitly says "no format restrictions" on skill bodies. Forcing a five-slot schema would require rewriting all existing skills and fight the format rather than enhancing it.

## Afterlife

Available as an optional **analysis lens** — you can ask ToolMaster to decompose any skill into intake/lens/core/guardrail/effect for inspection purposes. But it's not a requirement for authoring or storing skills.

The original slots:
1. Intake — how the skill receives input
2. Lens — raw input → structured meaning
3. Core — the actual transformation or decision
4. Guardrail — sanity check before output
5. Effect — what touches the outside world

These remain useful as a mental model for understanding skills, not as a schema for writing them.
