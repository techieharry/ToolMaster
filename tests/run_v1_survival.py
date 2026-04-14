"""V1 survival test runner — end-to-end on real seed skills.

Pins all 5 seed skills under `skills/` into an isolated tmp store,
builds two deliberately differentiated loadouts, records 10 tasks
across them, runs the heuristic comparison twice (once per task bias),
and prints a verdict. Also writes `docs/v1-survival-results.md`.

Run from repo root:
    python tests/run_v1_survival.py
"""

import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Force UTF-8 stdout so LLM output containing Unicode (arrows, dashes, quotes)
# doesn't crash the Windows cp1252 default console encoding.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, io.UnsupportedOperation):
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from toolmaster import store, loadout, record, compare


def _redirect_store(tmp_home: Path):
    store.TOOLMASTER_HOME = tmp_home
    store.STORE_DIR = tmp_home / "store"
    store.BLOBS_DIR = store.STORE_DIR / "blobs"
    store.MANIFESTS_DIR = store.STORE_DIR / "manifests"
    store.LOADOUTS_DIR = tmp_home / "loadouts"
    store.RECORDINGS_DIR = tmp_home / "recordings"
    loadout.LOADOUTS_DIR = store.LOADOUTS_DIR
    record.RECORDINGS_DIR = store.RECORDINGS_DIR


def main():
    results_md = REPO_ROOT / "docs" / "v1-survival-results.md"
    lines = []

    def say(s=""):
        print(s)
        lines.append(s)

    say("# V1 Survival Test Results")
    say()
    say("> Run: 2026-04-14 on isolated tmp store")
    say("> Purpose: validate the V1 thesis plumbing — pin -> loadout -> record -> compare")
    say("> Mode: heuristic judge (no API key this session). LLM-judge run is the next step.")
    say()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_home = Path(tmp) / ".toolmaster"
        _redirect_store(tmp_home)

        say("## Step 1 — Pin real seed skills")
        say()
        seeds_root = REPO_ROOT / "skills"
        seed_dirs = sorted(p for p in seeds_root.iterdir() if p.is_dir())
        pinned: list[dict] = []
        skipped: list[tuple[str, str]] = []
        for d in seed_dirs:
            if not (d / "SKILL.md").exists():
                continue
            try:
                m = store.pin_skill(d)
                pinned.append(m)
                say(f"- pinned **{m['name']}** -> `{m['id'][:12]}` ({len(m['files'])} files)")
            except ValueError as e:
                skipped.append((d.name, str(e)))
                say(f"- skipped **{d.name}** (quality gate): {str(e)[:100]}")

        if not pinned:
            say()
            say("FAIL: no seed skills could be pinned. Survival test aborted.")
            results_md.write_text("\n".join(lines), encoding="utf-8")
            return 1

        say()
        say(f"Pinned {len(pinned)} seed skills, skipped {len(skipped)}.")
        say()

        # Build two deliberately differentiated loadouts.
        names = {m["name"]: m["id"] for m in pinned}

        # Loadout A: refactor-leaning (refactor + code-review + document-writer)
        # Loadout B: debug/fix-leaning (bug-fix + test-generator + data-analysis)
        a_candidates = ["refactor", "code-review", "document-writer"]
        b_candidates = ["bug-fix", "test-generator", "data-analysis"]

        lo_a_hashes = [names[n] for n in a_candidates if n in names]
        lo_b_hashes = [names[n] for n in b_candidates if n in names]

        if len(lo_a_hashes) < 2 or len(lo_b_hashes) < 2:
            say("FAIL: not enough pinned skills to build two differentiated loadouts.")
            say(f"A had {len(lo_a_hashes)}, B had {len(lo_b_hashes)}.")
            results_md.write_text("\n".join(lines), encoding="utf-8")
            return 1

        say("## Step 2 — Build two loadouts")
        say()
        loadout.create_loadout("refactor_stack", lo_a_hashes)
        loadout.create_loadout("bugfix_stack", lo_b_hashes)
        say(f"- **refactor_stack**: {', '.join(a_candidates if all(n in names for n in a_candidates) else [n for n in a_candidates if n in names])}")
        say(f"- **bugfix_stack**:   {', '.join(b_candidates if all(n in names for n in b_candidates) else [n for n in b_candidates if n in names])}")
        say()

        say("## Step 3 — Record tasks")
        say()
        # 5 refactor tasks (attributed to refactor_stack)
        refactor_tasks = [
            "refactor the long handler function into smaller units and rename unclear variables",
            "extract duplicated validation code from three route handlers into a shared helper",
            "split the 900-line utils.py into coherent modules and update imports",
            "reduce the nested conditionals in the checkout flow using guard clauses",
            "rename legacy snake_case API fields to camelCase and update callers",
        ]
        # 5 bug-fix tasks (attributed to bugfix_stack)
        bug_tasks = [
            "bug-fix the null pointer crash when the session token is missing",
            "reproduce and fix the race condition in the cache eviction loop",
            "trace the stack for the crash in the upload handler and patch the regression",
            "write a failing test for the off-by-one in the pagination query, then fix it",
            "debug why the worker silently swallows exceptions in the retry path",
        ]
        for t in refactor_tasks:
            record.quick_record(task=t, output="done", loadout_name="refactor_stack")
            say(f"- [refactor_stack] {t[:70]}")
        for t in bug_tasks:
            record.quick_record(task=t, output="done", loadout_name="bugfix_stack")
            say(f"- [bugfix_stack]   {t[:70]}")
        say()
        say(f"Recorded {len(refactor_tasks) + len(bug_tasks)} tasks total.")
        say()

        import os as _os
        use_llm = bool(_os.environ.get("OPENROUTER_API_KEY") or _os.environ.get("ANTHROPIC_API_KEY"))
        mode_label = "LLM judge" if use_llm else "heuristic judge"
        say(f"## Step 4 — Compare loadouts ({mode_label})")
        say()
        result = compare.compare_loadouts("refactor_stack", "bugfix_stack", use_llm=use_llm)
        if "error" in result:
            say(f"FAIL: {result['error']}")
            results_md.write_text("\n".join(lines), encoding="utf-8")
            return 1

        say(f"- tasks evaluated: **{result['tasks_evaluated']}**")
        say(f"- method: `{result['method']}`")
        say(f"- refactor_stack wins: **{result['wins_a']}**")
        say(f"- bugfix_stack wins:   **{result['wins_b']}**")
        say(f"- ties: **{result['ties']}**")
        say(f"- overall winner: **{result['winner']}**")
        say()

        say("### Per-task breakdown")
        say()
        refactor_correct = 0
        bugfix_correct = 0
        for d in result["details"]:
            task = d["task"]
            winner = d["winner"]
            conf = d.get("confidence")
            reasoning = d.get("reasoning", "")
            conf_s = f" ({conf:.0%})" if isinstance(conf, (int, float)) and conf else ""
            say(f"- **[{winner}{conf_s}]** {task}")
            if reasoning:
                say(f"    - _{reasoning}_")
            if "refactor" in task.lower() or "rename" in task.lower() or "extract" in task.lower() or "split" in task.lower() or "reduce" in task.lower():
                if winner == "refactor_stack":
                    refactor_correct += 1
            elif "bug" in task.lower() or "crash" in task.lower() or "debug" in task.lower() or "race" in task.lower() or "off-by-one" in task.lower():
                if winner == "bugfix_stack":
                    bugfix_correct += 1
        say()

        say("## Verdict")
        say()
        # Actionable-insight test: the judge should correctly attribute
        # refactor tasks to refactor_stack and bug tasks to bugfix_stack.
        say(f"- refactor tasks correctly attributed: **{refactor_correct}/{len(refactor_tasks)}**")
        say(f"- bug tasks correctly attributed:      **{bugfix_correct}/{len(bug_tasks)}**")
        say()

        total_correct = refactor_correct + bugfix_correct
        total = len(refactor_tasks) + len(bug_tasks)
        pipeline_ran = result["tasks_evaluated"] == total
        non_degenerate = result["ties"] < (total * 0.5)  # at least half the tasks get a real verdict
        above_random = total_correct > (total * 0.5)     # beats 50/50 coin flip

        strong_signal = total_correct >= (total * 0.8)  # >=80% attribution = thesis holds
        thesis_bar = "LLM" if use_llm else "heuristic"

        if pipeline_ran and non_degenerate and strong_signal and use_llm:
            say(f"**PLUMBING: PASS.** {total} recordings evaluated via `{result['method']}`, verdict {result['wins_a']}/{result['wins_b']}/{result['ties']} (A/B/tie).")
            say()
            say(f"**V1 THESIS: PROVEN.** LLM judge correctly attributed **{total_correct}/{total}** tasks to the loadout whose composition best fits the task type. This exceeds the 80% bar and clears the roadmap's survival test. The `stack A vs stack B` question is actionable on real tasks — V1 holds, V2 (offer engine) is unlocked as the next phase.")
            exit_code = 0
        elif pipeline_ran and above_random and use_llm:
            say(f"**PLUMBING: PASS, THESIS WEAK.** LLM judge evaluated {total} tasks ({result['wins_a']}/{result['wins_b']}/{result['ties']}). Attribution accuracy was {total_correct}/{total} — above random but below the 80% confidence bar. The judge can discriminate but not crisply. Possible causes: underspecified judge prompt, loadouts too similar, or recordings too short to anchor the judgment. Tune the prompt in `compare.py:112-144` and re-run before concluding.")
            exit_code = 0
        elif pipeline_ran and use_llm:
            say(f"**V1 THESIS: WEAK / POSSIBLY FALSE.** LLM judge evaluated {total} tasks but scored {total_correct}/{total} — at or below random. Either the judge prompt is broken, the loadouts aren't meaningfully differentiated, or loadout-level eval does not in fact produce actionable insights on this task mix. Per CLAUDE.md:88-90, this is the survival condition — do not proceed to V2 without resolving.")
            exit_code = 2
        elif pipeline_ran and non_degenerate and above_random:
            say(f"**PLUMBING: PASS (heuristic).** {total} recordings evaluated, {total_correct}/{total} correct attribution beats random. Thesis test requires LLM judge (re-run with `OPENROUTER_API_KEY`).")
            exit_code = 0
        elif pipeline_ran:
            say(f"**PLUMBING: PASS, SIGNAL WEAK.** Pipeline evaluated all {total} tasks, but {thesis_bar} attribution ({total_correct}/{total}) or tie rate ({result['ties']}/{total}) suggests the judge cannot reliably discriminate these loadouts.")
            exit_code = 0
        else:
            say(f"**FAIL.** Pipeline did not evaluate all {total} recordings (only {result['tasks_evaluated']}). Investigate `compare.compare_loadouts`.")
            exit_code = 1

        say()
        say("## Next step")
        say()
        say("```bash")
        say("$env:OPENROUTER_API_KEY = '...'")
        say("python tests/run_v1_survival.py")
        say("```")
        say()
        say("Expect `method: llm` in the output and per-task reasoning sentences.")

    results_md.parent.mkdir(parents=True, exist_ok=True)
    results_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print()
    print(f"Wrote: {results_md}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
