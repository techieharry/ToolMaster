# ToolMaster Architecture

## What it is

ToolMaster is an autonomous, self-improving skill infrastructure that manages a global toolbox across all Claude Code projects. It watches what agents build, learns what works, scouts GitHub for better techniques, security-audits everything, re-engineers weak tools, and proposes upgrades — all without human intervention.

The toolbox only grows. Every agent session contributes. Every tool gets measured. The best survive. The worst get re-engineered.

---

## System overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        TOOLMASTER SYSTEM                             │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Project  │  │ Project  │  │ Project  │  │ Project  │   ...×12    │
│  │ myagency │  │ PSX Pulse│  │ Wife Bot │  │ theforge │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
│       │              │              │              │                  │
│       ▼              ▼              ▼              ▼                  │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    HOOK LAYER (settings.json)                │    │
│  │                                                              │    │
│  │  Notification hook → auto-checkin (session start)            │    │
│  │  PreToolUse hook   → write-check (SKILL.md guard)           │    │
│  │  Stop hook         → auto-return + auto-log (session end)   │    │
│  │                                                              │    │
│  │  Agents can't bypass this. Hooks fire automatically.         │    │
│  └──────────────────────────────┬───────────────────────────────┘    │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    PROTOCOL LAYER                            │    │
│  │                                                              │    │
│  │  checkin   → agent starts, gets toolbox state + proposals    │    │
│  │  checkout  → agent checks for existing tools before building │    │
│  │  used      → agent reports using a toolbox tool              │    │
│  │  created   → agent built something new (auto-pinned)         │    │
│  │  forked    → agent improved existing tool (lineage tracked)  │    │
│  │  return    → session archived, compliance scored             │    │
│  │                                                              │    │
│  │  Structured handshake. Watcher knows what agents actually do.│    │
│  └──────────────────────────────┬───────────────────────────────┘    │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                  GLOBAL STORE (~/.toolmaster/)               │    │
│  │                                                              │    │
│  │  store/blobs/      → content-addressed file blobs (SHA-256)  │    │
│  │  store/manifests/  → skill version manifests (hash → files)  │    │
│  │  loadouts/         → named skill stacks (JSON)               │    │
│  │  recordings/       → task recordings from all projects       │    │
│  │  proposals/        → pending tool upgrade proposals          │    │
│  │  lineage.json      → fork chains between skill versions      │    │
│  │                                                              │    │
│  │  Single source of truth. All projects read/write here.       │    │
│  └──────────────────────────────┬───────────────────────────────┘    │
│                                 │                                    │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    WATCHER v3 (background daemon)            │    │
│  │                    PID at ~/.toolmaster/watcher.pid           │    │
│  │                                                              │    │
│  │  ┌────────────────────────────────────────────────────────┐  │    │
│  │  │ POLL (every 30s)                                       │  │    │
│  │  │  Read data/logs/ from all 12 projects                  │  │    │
│  │  │  Extract quality signals:                              │  │    │
│  │  │    • edit distance (how much human changed AI output)  │  │    │
│  │  │    • rejection rate (sections thrown away)              │  │    │
│  │  │    • approval time (how long to review)                │  │    │
│  │  │    • client satisfaction (1-5 rating)                   │  │    │
│  │  │  Record in global store                                │  │    │
│  │  │  Update global insights                                │  │    │
│  │  └────────────────────────────────────────────────────────┘  │    │
│  │                                                              │    │
│  │  ┌────────────────────────────────────────────────────────┐  │    │
│  │  │ SYNC (every 5 min)                                     │  │    │
│  │  │                                                        │  │    │
│  │  │  PULL: Harvest new skills from all projects            │  │    │
│  │  │    Scan skills/, .claude/skills/, .agents/skills/      │  │    │
│  │  │    Auto-pin any new/modified SKILL.md to global store  │  │    │
│  │  │    Agent creates tool → toolbox grows automatically    │  │    │
│  │  │                                                        │  │    │
│  │  │  PUSH: Distribute to all projects                      │  │    │
│  │  │    TOOLMASTER_DIGEST.md → proven tools + performance   │  │    │
│  │  │    TOOLMASTER_AGENT_PROMPT.md → latest instructions    │  │    │
│  │  │    CLAUDE.md enforcement → protocol injection          │  │    │
│  │  │    Proposals → queued upgrades for agent checkin       │  │    │
│  │  └────────────────────────────────────────────────────────┘  │    │
│  │                                                              │    │
│  │  ┌────────────────────────────────────────────────────────┐  │    │
│  │  │ SCOUT (every 5 min)                                    │  │    │
│  │  │                                                        │  │    │
│  │  │  SEARCH: GitHub repos for skill patterns               │  │    │
│  │  │    Watched repos: anthropics/skills, obra/superpowers,  │  │    │
│  │  │    wshobson/agents, agentskills/agentskills, etc.      │  │    │
│  │  │    Rotating search queries for new repos               │  │    │
│  │  │    Skip already-audited skills                         │  │    │
│  │  │                                                        │  │    │
│  │  │  AUDIT: LLM security + relevance analysis              │  │    │
│  │  │    ┌──────────────────────────────────────────────┐    │  │    │
│  │  │    │ Layer 1: STATIC PRE-SCAN (free, instant)    │    │  │    │
│  │  │    │  Regex: prompt injection, data exfil,       │    │  │    │
│  │  │    │  credential refs, obfuscated code,          │    │  │    │
│  │  │    │  dangerous shell commands                   │    │  │    │
│  │  │    │  3+ flags → auto-reject                     │    │  │    │
│  │  │    ├──────────────────────────────────────────────┤    │  │    │
│  │  │    │ Layer 2: LLM AUDIT (Haiku via OpenRouter)   │    │  │    │
│  │  │    │  Relevance, overlap, quality comparison,    │    │  │    │
│  │  │    │  extractable techniques, deep security      │    │  │    │
│  │  │    │  analysis (injections, overrides, exfil)    │    │  │    │
│  │  │    ├──────────────────────────────────────────────┤    │  │    │
│  │  │    │ Layer 3: SAFETY GATE (code, free)           │    │  │    │
│  │  │    │  unsafe → REJECT (never enters toolbox)     │    │  │    │
│  │  │    │  caution → extract techniques only          │    │  │    │
│  │  │    │  safe → full import or extraction           │    │  │    │
│  │  │    └──────────────────────────────────────────────┘    │  │    │
│  │  │                                                        │  │    │
│  │  │  RE-ENGINEER: Upgrade weak tools (Sonnet)              │  │    │
│  │  │    Find tools with high edit distance                  │  │    │
│  │  │    Merge techniques from safe audited external skills  │  │    │
│  │  │    Produce upgraded SKILL.md                           │  │    │
│  │  │                                                        │  │    │
│  │  │  PROPOSE: Queue for agents                             │  │    │
│  │  │    Import proposals (new tools from GitHub)            │  │    │
│  │  │    Re-engineer proposals (upgraded existing tools)     │  │    │
│  │  │    Distributed to all project proposal queues          │  │    │
│  │  │    Agents see on next checkin                          │  │    │
│  │  └────────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │                    EVALUATION LAYER                          │    │
│  │                                                              │    │
│  │  suggest   → rank tools by task relevance + performance     │    │
│  │  compare   → LLM judge: loadout A vs loadout B              │    │
│  │  proven    → list battle-tested tools (low edit, high use)  │    │
│  │                                                              │    │
│  │  V2 triggers at 50 runs per loadout.                        │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Model routing (OpenRouter)

Different models for different cognitive tasks. Cheap where speed matters, expensive where quality matters.

```
┌─────────────────┬──────────────────────────┬───────────┬───────────────────────┐
│ Task            │ Model                    │ Cost/call │ Why this model        │
├─────────────────┼──────────────────────────┼───────────┼───────────────────────┤
│ Audit skills    │ claude-haiku-4.5         │ ~$0.001   │ Fast classification   │
│ Compare loadouts│ claude-haiku-4.5         │ ~$0.001   │ Structured judgment   │
│ Suggest tools   │ claude-haiku-4.5         │ ~$0.001   │ Fast ranking          │
│ Re-engineer     │ claude-sonnet-4          │ ~$0.01    │ Creative rewriting    │
├─────────────────┼──────────────────────────┼───────────┼───────────────────────┤
│ Override env    │ TOOLMASTER_AUDIT_MODEL   │           │                       │
│                 │ TOOLMASTER_REENGINEER_MODEL          │                       │
│                 │ TOOLMASTER_COMPARE_MODEL │           │                       │
│                 │ TOOLMASTER_SUGGEST_MODEL │           │                       │
└─────────────────┴──────────────────────────┴───────────┴───────────────────────┘
```

---

## Data flow

```
                    AGENTS BUILD TOOLS
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   Project A          Project B          Project C
   creates             forks              uses
   email-seq skill     social-posts v2    strategy-doc
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────────────────────────────────────────┐
   │              GLOBAL STORE                    │
   │  email-seq (new)                             │
   │  social-posts v2 (fork of v1, lineage tracked)│
   │  strategy-doc (usage +1)                     │
   └──────────────────┬──────────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────┐
   │              WATCHER                         │
   │                                              │
   │  Sees: email-seq is new → add to digest      │
   │  Sees: social-posts v2 forked → track lineage│
   │  Sees: strategy-doc used again → boost score  │
   │                                              │
   │  Meanwhile, scout found a better email        │
   │  pattern on GitHub → audit → safe →           │
   │  re-engineer email-seq with new techniques    │
   │  → propose email-seq v2 to all projects       │
   └──────────────────┬──────────────────────────┘
                      │
                      ▼
   ┌─────────────────────────────────────────────┐
   │         DISTRIBUTED TO ALL PROJECTS          │
   │                                              │
   │  TOOLMASTER_DIGEST.md:                       │
   │    "email-seq: 3x used, 15% edit — proven"  │
   │    "social-posts v2: 2x used, 30% edit"     │
   │    "strategy-doc: 8x used, 0% edit — gold"  │
   │                                              │
   │  Proposals:                                  │
   │    "email-seq v2 available — re-engineered    │
   │     with patterns from obra/superpowers"      │
   │                                              │
   │  CLAUDE.md enforcement:                      │
   │    "BEFORE building, run toolmaster checkout" │
   └─────────────────────────────────────────────┘
                      │
                      ▼
               AGENTS USE TOOLS
          (cycle repeats, toolbox grows)
```

---

## File system layout

```
~/.toolmaster/                              GLOBAL STATE
├── store/
│   ├── blobs/                              Content-addressed files (SHA-256)
│   └── manifests/                          Skill manifests (hash → file tree)
├── loadouts/                               Named skill stacks
├── recordings/                             Task recordings from all projects
├── proposals/                              Pending upgrade proposals
├── lineage.json                            Fork chains (child → parent hash)
├── global_watcher_state.json               Processed log tracking
├── global_insights.json                    Cross-project quality metrics
├── harvest_state.json                      Which skills have been harvested
├── scout_state.json                        Scout progress + cached audits
├── scout.log                               Scout activity log
├── watcher.pid                             Background daemon PID
└── watcher.log                             Watcher activity log

~/Documents/claude/ToolMaster/              SOURCE CODE
├── ARCHITECTURE.md                         ← YOU ARE HERE
├── CLAUDE.md                               Project concept + decisions
├── TOOLMASTER_AGENT_PROMPT.md              Prompt for agents (distributed)
├── roadmap.md                              Phased build plan
├── pyproject.toml                          Python package config
├── toolmaster/                             Python package
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                              CLI entry point (20 commands)
│   ├── store.py                            Content-addressed store
│   ├── loadout.py                          Loadout composition
│   ├── record.py                           Task recording
│   ├── compare.py                          LLM loadout comparison
│   ├── suggest.py                          Skill recommendation engine
│   ├── protocol.py                         Agent session protocol
│   ├── sync.py                             Cross-project sync engine
│   ├── scout.py                            GitHub scouting + audit + re-engineering
│   └── global_watcher.py                   Background daemon
├── hooks/
│   ├── session-start.sh                    Notification hook (auto-checkin)
│   ├── session-end.sh                      Stop hook (auto-return + log)
│   ├── pre-write-check.sh                  PreToolUse hook (SKILL.md guard)
│   ├── auto-log.sh                         Legacy stop hook (thin logging)
│   └── run-watcher.sh                      Daemon control (start/stop/status)
├── docs/                                   Research + analysis
│   ├── competitive-analysis.md
│   ├── immutable-parts.md
│   ├── roguelike-selection.md
│   ├── toolbox-master.md
│   └── five-slot-grammar.md                (killed)
└── tests/

~/Documents/claude/*/                       EVERY PROJECT
├── toolmaster/ → symlink                   Points to ToolMaster source
├── data/
│   ├── logs/*.json                         Generation logs (agents + hooks write)
│   ├── sessions/*.json                     Archived protocol sessions
│   ├── insights/                           Project-local insights
│   ├── toolmaster_session.json             Active session manifest
│   └── toolmaster_proposals.json           Queued proposals from scout
├── TOOLMASTER_AGENT_PROMPT.md              Agent instructions (auto-synced)
├── TOOLMASTER_DIGEST.md                    Toolbox state (auto-synced)
└── CLAUDE.md                               Has enforcement block (auto-injected)
```

---

## CLI commands

```
STORE
  toolmaster pin <dir>              Pin a skill to the store
  toolmaster ls                     List all pinned skills
  toolmaster show <hash>            Show skill details
  toolmaster resolve <hash> <dir>   Reconstruct skill from store

LOADOUTS
  toolmaster loadout create <name> <hash...>   Create a skill stack
  toolmaster loadout show <name>               Show loadout
  toolmaster loadout list                      List all loadouts
  toolmaster loadout apply <name>              Inject into agent paths
  toolmaster loadout diff <A> <B>              Compare two loadouts

EVALUATION
  toolmaster compare <A> <B>        LLM judge: which loadout wins
  toolmaster suggest "task"         Find tools for a task
  toolmaster suggest --proven       List battle-tested tools
  toolmaster record -t "..." -l ... Manual task recording
  toolmaster recordings             List all recordings

PROTOCOL (agent session lifecycle)
  toolmaster checkin                Start session, get toolbox state
  toolmaster checkout "task"        Check for tools before building
  toolmaster used <name> <hash>     Report using a tool
  toolmaster created <dir>          Report creating a new tool
  toolmaster forked <dir> <parent>  Report improving a tool
  toolmaster return                 End session, archive, score

AUTONOMOUS
  toolmaster scout                  Run GitHub scout cycle manually
  toolmaster watch                  Start background daemon
  toolmaster watch --once           Run one poll cycle
  toolmaster watch --status         Show global insights
```

---

## Watcher schedule

```
Every 30s:   POLL     Read logs from 12 projects, extract signals
Every 5 min: SYNC     Harvest skills, push digests, enforce CLAUDE.md
Every 5 min: SCOUT    Search GitHub, audit, security-gate, re-engineer, propose
```

---

## Security model

External code goes through three layers before entering the toolbox:

```
EXTERNAL SKILL (from GitHub)
         │
         ▼
┌─────────────────────────────────────┐
│ LAYER 1: Static pre-scan (free)     │
│                                     │
│ Regex patterns for:                 │
│ • Prompt injection                  │
│   "ignore previous instructions"    │
│   "you are now", "new instructions" │
│ • Data exfiltration                 │
│   curl, wget, fetch, webhooks       │
│ • Credential references             │
│   api_key, password, bearer tokens  │
│ • Code obfuscation                  │
│   eval(), exec(), base64 encoding   │
│ • Dangerous shell                   │
│   rm -rf, sudo, chmod 777           │
│                                     │
│ 3+ flags → AUTO-REJECT              │
└────────────────┬────────────────────┘
                 │ passed
                 ▼
┌─────────────────────────────────────┐
│ LAYER 2: LLM audit (Haiku)         │
│                                     │
│ Deep analysis:                      │
│ • External URL injection vectors    │
│ • Agent instruction manipulation    │
│ • Hidden role overrides             │
│ • Safety boundary bypasses          │
│ • Obfuscated payload detection      │
│                                     │
│ Verdict: safe / caution / unsafe    │
└────────────────┬────────────────────┘
                 │ verdict
                 ▼
┌─────────────────────────────────────┐
│ LAYER 3: Safety gate (code)         │
│                                     │
│ unsafe  → REJECTED (logged, never   │
│           enters toolbox)           │
│ caution → extract techniques ONLY   │
│           (no direct import)        │
│ safe    → full import or extraction │
└─────────────────────────────────────┘
```

---

## How the toolbox compounds

```
Week 1:   4 skills, seeded from myagency
Week 2:   15 skills (agents built + scout imported)
Week 4:   30 skills, 50 recordings, first weak tools re-engineered
Month 2:  60+ skills, scout has audited 200+ external, 10 re-engineered
Month 3:  V2 threshold hit — loadout comparison produces statistical results
Month 6:  100+ skills, offer engine (V2) auto-suggests loadouts per task type

The more agents work → the more tools exist
The more tools exist → the more agents reuse instead of regenerate
The more reuse → the less tokens spent
The less tokens spent → the more agents can work
                                    ↻
```

---

## What was killed and why

| Killed | Why |
|---|---|
| Five-slot grammar | Fights the ecosystem. Everyone uses freeform markdown. |
| Composition operators | Skills aren't functions. Chain/parallel assumes typed I/O. |
| Monolithic toolbox master | Decomposed into poll + sync + scout + protocol. |
| B2C approach (MyAgency) | Economics don't work. B2B (agency tool) survives. |
| Website generation | AI does copy/strategy, not visual design. |

---

## Running the system

```bash
# Start the watcher daemon (runs in background)
~/Documents/claude/ToolMaster/hooks/run-watcher.sh start

# Check status
~/Documents/claude/ToolMaster/hooks/run-watcher.sh status

# Stop
~/Documents/claude/ToolMaster/hooks/run-watcher.sh stop

# Manual scout run
OPENROUTER_API_KEY="..." python3 -m toolmaster scout

# Check global insights
python3 -m toolmaster watch --status
```
