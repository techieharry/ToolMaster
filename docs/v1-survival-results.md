# V1 Survival Test Results

> Run: 2026-04-14 on isolated tmp store
> Purpose: validate the V1 thesis plumbing — pin -> loadout -> record -> compare
> Mode: heuristic judge (no API key this session). LLM-judge run is the next step.

## Step 1 — Pin real seed skills

- pinned **api-integration** -> `1799d7fe476b` (1 files)
- pinned **bug-fix** -> `f2226555d31b` (1 files)
- pinned **code-review** -> `4cc97e6acaa2` (1 files)
- pinned **data-analysis** -> `80a82321d6ff` (1 files)
- pinned **document-writer** -> `205000bde1a8` (1 files)
- pinned **refactor** -> `74a6d4d62f48` (1 files)
- pinned **test-generator** -> `d46bed122083` (1 files)

Pinned 7 seed skills, skipped 0.

## Step 2 — Build two loadouts

- **refactor_stack**: refactor, code-review, document-writer
- **bugfix_stack**:   bug-fix, test-generator, data-analysis

## Step 3 — Record tasks

- [refactor_stack] refactor the long handler function into smaller units and rename uncle
- [refactor_stack] extract duplicated validation code from three route handlers into a sh
- [refactor_stack] split the 900-line utils.py into coherent modules and update imports
- [refactor_stack] reduce the nested conditionals in the checkout flow using guard clause
- [refactor_stack] rename legacy snake_case API fields to camelCase and update callers
- [bugfix_stack]   bug-fix the null pointer crash when the session token is missing
- [bugfix_stack]   reproduce and fix the race condition in the cache eviction loop
- [bugfix_stack]   trace the stack for the crash in the upload handler and patch the regr
- [bugfix_stack]   write a failing test for the off-by-one in the pagination query, then 
- [bugfix_stack]   debug why the worker silently swallows exceptions in the retry path

Recorded 10 tasks total.

## Step 4 — Compare loadouts (heuristic judge)

- tasks evaluated: **10**
- method: `heuristic`
- refactor_stack wins: **4**
- bugfix_stack wins:   **4**
- ties: **2**
- overall winner: **tie**

### Per-task breakdown

- **[bugfix_stack (50%)]** write a failing test for the off-by-one in the pagination query, then fix it
    - _Heuristic: keyword overlap scores X=6, Y=14_
- **[refactor_stack (50%)]** extract duplicated validation code from three route handlers into a shared helpe
    - _Heuristic: keyword overlap scores X=8, Y=3_
- **[refactor_stack (50%)]** trace the stack for the crash in the upload handler and patch the regression
    - _Heuristic: keyword overlap scores X=6, Y=4_
- **[bugfix_stack (50%)]** bug-fix the null pointer crash when the session token is missing
    - _Heuristic: keyword overlap scores X=8, Y=4_
- **[refactor_stack (50%)]** rename legacy snake_case API fields to camelCase and update callers
    - _Heuristic: keyword overlap scores X=5, Y=3_
- **[tie (50%)]** debug why the worker silently swallows exceptions in the retry path
    - _Heuristic: keyword overlap scores X=3, Y=3_
- **[bugfix_stack (50%)]** reproduce and fix the race condition in the cache eviction loop
    - _Heuristic: keyword overlap scores X=4, Y=7_
- **[refactor_stack (50%)]** refactor the long handler function into smaller units and rename unclear variabl
    - _Heuristic: keyword overlap scores X=3, Y=7_
- **[bugfix_stack (50%)]** split the 900-line utils.py into coherent modules and update imports
    - _Heuristic: keyword overlap scores X=3, Y=2_
- **[tie (50%)]** reduce the nested conditionals in the checkout flow using guard clauses
    - _Heuristic: keyword overlap scores X=2, Y=2_

## Verdict

- refactor tasks correctly attributed: **3/5**
- bug tasks correctly attributed:      **3/5**

**PLUMBING: PASS (heuristic).** 10 recordings evaluated, 6/10 correct attribution beats random. Thesis test requires LLM judge (re-run with `OPENROUTER_API_KEY`).

## Next step

```bash
$env:OPENROUTER_API_KEY = '...'
python tests/run_v1_survival.py
```

Expect `method: llm` in the output and per-task reasoning sentences.
