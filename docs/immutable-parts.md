# Content-Addressed Skill Registry

## Model

- Every skill version = frozen SHA-256 hash of its directory contents
- Pin a skill → hash each file → produce manifest (file tree + content hashes) → manifest hash = version ID
- Skills never mutate in the store. Edits create new hashes.
- Agents pin to hashes, not names. Forks create new hashes.

## Store layout

```
~/.toolmaster/
├── store/
│   ├── blobs/          # content-addressed file blobs (sha256)
│   └── manifests/      # skill manifests (name, file tree, hashes)
├── loadouts/           # named loadout definitions (JSON)
└── recordings/         # recorded task sessions (JSON)
```

## Benefits

- Reproducible agent runs (pin loadout to exact hashes)
- Cache hits on stable prefixes (token savings at fleet scale)
- Instant rollback to any prior version
- Audit trail: which skill version produced which output
- Dedup: identical content across skills shares blobs

## Design decisions

- **Hash algorithm**: SHA-256 (standard, fast, collision-resistant)
- **Granularity**: Per-file blobs + per-skill manifest. Manifest hash is the skill version ID. Avoids the "typo creates new everything" problem — only changed files get new blob hashes, manifest updates to reflect.
- **Local-first**: `~/.toolmaster/store/` with no cloud dependency for V1. Remote push/pull is V2+.
- **Anthropic spec compatible**: stores standard SKILL.md directories unchanged. ToolMaster metadata lives in manifests, not in the skill files.
