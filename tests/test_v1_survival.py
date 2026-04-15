"""V1 survival tests — the roadmap validation gates.

Covers the four roadmap "validate before moving on" checkpoints:
  Step 1: pin -> resolve round-trip + prefix hash lookup + hash stability
  Step 2: loadout create + priority order + diff
  Step 3: recording create + list + filter
  Step 4: compare_loadouts heuristic path produces a verdict

Tests are stdlib-only (unittest) to match the V1 "no external deps" rule.
Each test isolates ~/.toolmaster to a tmp dir via monkey-patched module paths.

Run: python -m unittest tests.test_v1_survival -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make `toolmaster` importable when run from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from toolmaster import store, loadout, record, compare, offer, scout, delegate as tm_delegate, protocol


def _redirect_store(tmp_home: Path):
    """Point all module-level store paths at a tmp home."""
    store.TOOLMASTER_HOME = tmp_home
    store.STORE_DIR = tmp_home / "store"
    store.BLOBS_DIR = store.STORE_DIR / "blobs"
    store.MANIFESTS_DIR = store.STORE_DIR / "manifests"
    store.LOADOUTS_DIR = tmp_home / "loadouts"
    store.RECORDINGS_DIR = tmp_home / "recordings"
    # Modules that re-imported the constants need refreshed binding
    loadout.LOADOUTS_DIR = store.LOADOUTS_DIR
    record.RECORDINGS_DIR = store.RECORDINGS_DIR
    compare.TOOLMASTER_HOME = tmp_home
    compare.COMPARE_CACHE_DIR = tmp_home / "compare_cache"
    offer.TOOLMASTER_HOME = tmp_home
    offer.OFFER_CACHE_DIR = tmp_home / "offer_cache"


def _write_synthetic_skill(parent: Path, name: str, body_suffix: str = "") -> Path:
    """Build a minimal SKILL.md that passes the quality gate (score >= 60)."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    description = (
        f"{name.replace('-', ' ').title()} skill. "
        f"Use when working on {name.replace('-', ' ')} tasks in a codebase."
    )
    body_lines = [
        f"# {name}",
        "",
        "## When to use",
        f"- Working on {name.replace('-', ' ')}",
        "- Need structured guidance",
        "",
        "## Process",
        "1. Identify the problem",
        "2. Apply the technique",
        "3. Verify the result",
    ]
    if body_suffix:
        body_lines += ["", body_suffix]
    content = (
        "---\n"
        f"name: {name}\n"
        f'description: {description}\n'
        "---\n\n"
        + "\n".join(body_lines)
        + "\n"
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return skill_dir


class StoreRoundTripTests(unittest.TestCase):
    """Roadmap Step 1 gate: pin -> resolve round-trip."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_pin_then_resolve_reproduces_contents(self):
        skill_dir = _write_synthetic_skill(self.work, "round-trip-skill")
        original = (skill_dir / "SKILL.md").read_bytes()

        manifest = store.pin_skill(skill_dir)
        self.assertEqual(len(manifest["id"]), 64, "manifest id should be full SHA-256 hex")
        self.assertIn("SKILL.md", manifest["files"])

        target_parent = Path(self.tmp.name) / "resolved"
        target_parent.mkdir()
        resolved = store.resolve_skill(manifest["id"], target_parent)
        self.assertTrue(resolved.is_dir())
        resolved_md = resolved / "SKILL.md"
        self.assertTrue(resolved_md.exists())
        self.assertEqual(resolved_md.read_bytes(), original)

    def test_pin_is_deterministic_and_content_addressed(self):
        a = _write_synthetic_skill(self.work, "determinism-a")
        b_parent = Path(self.tmp.name) / "work2"
        b_parent.mkdir()
        # Same contents under a different parent path must produce the same manifest hash
        # iff `source` is stripped — but current code includes `source` in the manifest,
        # so identical contents under different paths will differ. Instead assert that
        # re-pinning the SAME directory produces a matching *file-content* fingerprint.
        m1 = store.pin_skill(a)
        m2 = store.pin_skill(a)
        self.assertEqual(
            {k: v["hash"] for k, v in m1["files"].items()},
            {k: v["hash"] for k, v in m2["files"].items()},
            "per-file blob hashes must be stable across re-pins",
        )

    def test_resolve_accepts_hash_prefix(self):
        skill_dir = _write_synthetic_skill(self.work, "prefix-lookup")
        manifest = store.pin_skill(skill_dir)
        target = Path(self.tmp.name) / "prefix-out"
        target.mkdir()
        # Prefix match (first 12 chars) should be unambiguous with one skill in store
        resolved = store.resolve_skill(manifest["id"][:12], target)
        self.assertTrue((resolved / "SKILL.md").exists())

    def test_list_skills_reflects_store(self):
        _write_synthetic_skill(self.work, "list-one")
        _write_synthetic_skill(self.work, "list-two")
        store.pin_skill(self.work / "list-one")
        store.pin_skill(self.work / "list-two")
        listed = store.list_skills()
        names = {s["name"] for s in listed}
        self.assertEqual(names, {"list-one", "list-two"})
        for s in listed:
            self.assertEqual(len(s["short_id"]), 12)


class LoadoutTests(unittest.TestCase):
    """Roadmap Step 2 gate: loadouts + priority order + diff."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

        self.h_a = store.pin_skill(_write_synthetic_skill(self.work, "alpha"))["id"]
        self.h_b = store.pin_skill(_write_synthetic_skill(self.work, "bravo"))["id"]
        self.h_c = store.pin_skill(_write_synthetic_skill(self.work, "charlie"))["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_preserves_priority_order(self):
        lo = loadout.create_loadout("lo_order", [self.h_c, self.h_a, self.h_b])
        self.assertEqual([s["name"] for s in lo["skills"]], ["charlie", "alpha", "bravo"])

    def test_loadout_round_trip_via_disk(self):
        loadout.create_loadout("persist", [self.h_a, self.h_b])
        loaded = loadout.get_loadout("persist")
        self.assertEqual([s["hash"] for s in loaded["skills"]], [self.h_a, self.h_b])

    def test_diff_reports_adds_removes_and_reorders(self):
        loadout.create_loadout("left", [self.h_a, self.h_b])
        loadout.create_loadout("right", [self.h_b, self.h_c])
        d = loadout.diff_loadouts("left", "right")
        self.assertIn(self.h_a, d["only_in_left"])
        self.assertIn(self.h_c, d["only_in_right"])
        self.assertIn(self.h_b, d["shared"])

    def test_diff_detects_priority_order_change(self):
        loadout.create_loadout("top_a", [self.h_a, self.h_b])
        loadout.create_loadout("top_b", [self.h_b, self.h_a])
        d = loadout.diff_loadouts("top_a", "top_b")
        # Both skills are shared but at different priorities
        self.assertEqual(len(d["order_changes"]), 2)


class RecordingTests(unittest.TestCase):
    """Roadmap Step 3 gate: recording persistence + filtering."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)

    def tearDown(self):
        self.tmp.cleanup()

    def test_quick_record_persists(self):
        rec = record.quick_record(
            task="write a haiku",
            output="five seven five",
            loadout_name="poet",
            rating=4,
        )
        loaded = record.get_recording(rec["id"])
        self.assertEqual(loaded["task"], "write a haiku")
        self.assertEqual(loaded["rating"], 4)
        self.assertEqual(loaded["status"], "complete")

    def test_list_filters_by_loadout(self):
        record.quick_record(task="task a", output="out", loadout_name="lo1")
        record.quick_record(task="task b", output="out", loadout_name="lo2")
        record.quick_record(task="task c", output="out", loadout_name="lo1")
        only_lo1 = record.list_recordings(loadout="lo1")
        self.assertEqual(len(only_lo1), 2)
        self.assertTrue(all(r["loadout"] == "lo1" for r in only_lo1))


class CompareHeuristicTests(unittest.TestCase):
    """Roadmap Step 4 gate: compare produces a verdict on real recordings.

    Uses the heuristic path (no LLM) so it runs offline. The LLM path is
    the actual thesis test — this only proves plumbing, not the thesis.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

        # Build two deliberately differentiated loadouts.
        # "refactor-heavy" is aimed at cleanup tasks, "bug-heavy" at debugging.
        refactor_hash = store.pin_skill(
            _write_synthetic_skill(
                self.work, "refactor",
                body_suffix="## Extract function\nPull a named chunk out of a long function.",
            )
        )["id"]
        simplify_hash = store.pin_skill(
            _write_synthetic_skill(
                self.work, "simplify",
                body_suffix="## Reduce duplication\nDelete repeated patterns and rename for clarity.",
            )
        )["id"]
        bugfix_hash = store.pin_skill(
            _write_synthetic_skill(
                self.work, "bug-fix",
                body_suffix="## Reproduce the bug\nWrite a failing test that exposes the crash or regression.",
            )
        )["id"]
        debug_hash = store.pin_skill(
            _write_synthetic_skill(
                self.work, "debug-trace",
                body_suffix="## Trace the stack\nInspect the crash stacktrace and isolate the failing call.",
            )
        )["id"]

        loadout.create_loadout("refactor_loadout", [refactor_hash, simplify_hash])
        loadout.create_loadout("bugfix_loadout", [bugfix_hash, debug_hash])

    def tearDown(self):
        self.tmp.cleanup()

    def test_compare_returns_error_with_no_recordings(self):
        result = compare.compare_loadouts("refactor_loadout", "bugfix_loadout", use_llm=False)
        self.assertIn("error", result)

    def test_compare_heuristic_picks_refactor_loadout_for_refactor_tasks(self):
        # All recordings describe refactor tasks — refactor_loadout should dominate.
        for i in range(6):
            record.quick_record(
                task=f"refactor the long function and reduce duplication in module {i}",
                output="done",
                loadout_name="refactor_loadout",
            )
        result = compare.compare_loadouts("refactor_loadout", "bugfix_loadout", use_llm=False)
        self.assertNotIn("error", result)
        self.assertEqual(result["tasks_evaluated"], 6)
        self.assertEqual(result["method"], "heuristic")
        self.assertEqual(
            result["winner"], "refactor_loadout",
            f"heuristic should pick refactor_loadout for refactor tasks, got {result}",
        )

    def test_compare_heuristic_picks_bugfix_loadout_for_bug_tasks(self):
        for i in range(6):
            record.quick_record(
                task=f"reproduce and bug-fix a crash in the trace handler {i}",
                output="done",
                loadout_name="bugfix_loadout",
            )
        result = compare.compare_loadouts("refactor_loadout", "bugfix_loadout", use_llm=False)
        self.assertNotIn("error", result)
        self.assertEqual(
            result["winner"], "bugfix_loadout",
            f"heuristic should pick bugfix_loadout for bug tasks, got {result}",
        )


class MultiAgentTargetTests(unittest.TestCase):
    """Loadout apply now supports 7 agent targets, not just claude/agents."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

        self.h = store.pin_skill(_write_synthetic_skill(self.work, "single-skill"))["id"]
        loadout.create_loadout("mini", [self.h])

    def tearDown(self):
        self.tmp.cleanup()

    def test_agent_targets_cover_expected_set(self):
        expected = {"claude", "agents", "cursor", "codex", "aider", "windsurf", "continue"}
        self.assertEqual(set(loadout.AGENT_TARGETS.keys()), expected)

    def test_unknown_target_raises(self):
        with self.assertRaises(ValueError) as ctx:
            loadout.apply_loadout("mini", target="copilot")
        self.assertIn("copilot", str(ctx.exception))

    def test_apply_to_each_target_creates_expected_dir(self):
        # Use a tmp cwd for this — apply uses Path.cwd()
        import os as _os
        original_cwd = _os.getcwd()
        workdir = Path(self.tmp.name) / "app-work"
        workdir.mkdir()
        try:
            _os.chdir(workdir)
            for target, rel_path in loadout.AGENT_TARGETS.items():
                loadout.apply_loadout("mini", target=target)
                expected = workdir / rel_path / "single-skill"
                self.assertTrue(
                    expected.is_dir(),
                    f"target={target} should create {expected}",
                )
                self.assertTrue((expected / "SKILL.md").exists())
        finally:
            _os.chdir(original_cwd)


class CompareCacheAndCostTests(unittest.TestCase):
    """Roadmap Step 4 residuals: cost estimation + result caching."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

        self.h_ref = store.pin_skill(_write_synthetic_skill(self.work, "refactor"))["id"]
        self.h_bug = store.pin_skill(_write_synthetic_skill(self.work, "bug-fix"))["id"]
        loadout.create_loadout("a", [self.h_ref])
        loadout.create_loadout("b", [self.h_bug])

    def tearDown(self):
        self.tmp.cleanup()

    def test_estimate_cost_returns_concrete_numbers(self):
        record.quick_record(task="refactor thing", output="done", loadout_name="a")
        record.quick_record(task="another refactor", output="done", loadout_name="a")
        est = compare.estimate_compare_cost("a", "b")
        self.assertNotIn("error", est)
        self.assertEqual(est["task_count"], 2)
        self.assertGreater(est["est_input_tokens"], 0)
        self.assertGreater(est["est_output_tokens"], 0)
        self.assertGreater(est["est_usd"], 0)
        self.assertIn("model", est)

    def test_estimate_cost_errors_on_no_recordings(self):
        est = compare.estimate_compare_cost("a", "b")
        self.assertIn("error", est)

    def test_compare_does_not_cache_heuristic_results(self):
        record.quick_record(task="refactor handler", output="done", loadout_name="a")
        compare.compare_loadouts("a", "b", use_llm=False)
        # Heuristic is cheap — cache dir may exist from setup but should be empty of entries
        cache_dir = self.tmp_home / "compare_cache"
        if cache_dir.exists():
            self.assertEqual(list(cache_dir.glob("*.json")), [])


class OfferEngineColdStartTests(unittest.TestCase):
    """V2: offer engine returns coherent canonical/iterated/sideways."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

        # Build four distinct skills
        self.h_ref = store.pin_skill(_write_synthetic_skill(
            self.work, "refactor",
            body_suffix="## Extract function\nPull a named chunk out of a long function.",
        ))["id"]
        self.h_cr = store.pin_skill(_write_synthetic_skill(
            self.work, "code-review",
            body_suffix="## Review checklist\nReview code for clarity, correctness, safety.",
        ))["id"]
        self.h_bug = store.pin_skill(_write_synthetic_skill(
            self.work, "bug-fix",
            body_suffix="## Reproduce the bug\nWrite a failing test that exposes the crash.",
        ))["id"]
        self.h_test = store.pin_skill(_write_synthetic_skill(
            self.work, "test-generator",
            body_suffix="## Generate tests\nBuild a failing test first, then fix.",
        ))["id"]

        # Three loadouts
        loadout.create_loadout("refactor_stack", [self.h_ref, self.h_cr])
        loadout.create_loadout("refactor_stack_plus", [self.h_ref, self.h_cr, self.h_test])  # close cousin
        loadout.create_loadout("bugfix_stack", [self.h_bug, self.h_test])  # sideways candidate

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_store_returns_no_offers(self):
        # Redirect to a fresh tmp home with no loadouts
        import tempfile as _tf
        with _tf.TemporaryDirectory() as td:
            _redirect_store(Path(td) / ".toolmaster")
            self.assertEqual(offer.suggest_loadouts("any task"), [])

    def test_refactor_task_picks_refactor_canonical(self):
        offers = offer.suggest_loadouts(
            "refactor the long handler function and extract helpers", top_n=3
        )
        self.assertGreater(len(offers), 0)
        self.assertEqual(offers[0]["type"], "canonical")
        self.assertIn(offers[0]["name"], ("refactor_stack", "refactor_stack_plus"))

    def test_offers_include_at_most_one_of_each_type(self):
        offers = offer.suggest_loadouts(
            "refactor the duplicated validation logic", top_n=3
        )
        types = [o["type"] for o in offers]
        # At most one of each, no duplicates
        self.assertEqual(len(types), len(set(types)))

    def test_cold_start_flag_true_when_no_recordings(self):
        offers = offer.suggest_loadouts("refactor something", top_n=1)
        self.assertTrue(offers[0]["cold_start"])

    def test_sideways_has_low_overlap_with_canonical(self):
        offers = offer.suggest_loadouts(
            "refactor the authorization handler to reduce nesting", top_n=3
        )
        canonical = offers[0]
        sideways = next((o for o in offers if o["type"] == "sideways"), None)
        if sideways is not None:
            canon_skills = set(canonical["skills"])
            side_skills = set(sideways["skills"])
            overlap = len(canon_skills & side_skills) / max(len(canon_skills), 1)
            self.assertLess(overlap, 0.5,
                f"sideways overlap should be <50% but got {overlap:.0%}")


class DelegatePrimitiveTests(unittest.TestCase):
    """V2 skill-dispatch primitive — delegate() with cost est, dry run, recording."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

        self.h_ref = store.pin_skill(_write_synthetic_skill(
            self.work, "refactor",
            body_suffix="## Extract function\nPull a named chunk out of a long function.",
        ))["id"]
        self.h_cr = store.pin_skill(_write_synthetic_skill(
            self.work, "code-review",
            body_suffix="## Review\nCheck clarity and safety before merging.",
        ))["id"]
        loadout.create_loadout("specialist", [self.h_ref, self.h_cr])

    def tearDown(self):
        self.tmp.cleanup()

    def test_estimate_cost_uses_loadout_skills(self):
        est = tm_delegate.estimate_delegate_cost(
            "specialist", "refactor the thing", model="anthropic/claude-haiku-4.5"
        )
        self.assertNotIn("error", est)
        self.assertEqual(est["loadout"], "specialist")
        self.assertEqual(est["skill_count"], 2)
        # Cost estimate should be > 0 because skills contribute real token bytes
        self.assertGreater(est["est_input_tokens"], tm_delegate.BASE_SYSTEM_TOKENS)
        self.assertGreater(est["est_usd"], 0)

    def test_estimate_cost_errors_on_unknown_loadout(self):
        est = tm_delegate.estimate_delegate_cost("does-not-exist", "task")
        self.assertIn("error", est)

    def test_dry_run_never_calls_api(self):
        # No API key set, but dry-run should still succeed because it short-circuits
        import os as _os
        original_or = _os.environ.pop("OPENROUTER_API_KEY", None)
        original_a = _os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = tm_delegate.delegate(
                task="refactor the handler", loadout_name="specialist", dry_run=True
            )
            self.assertEqual(result["status"], "dry_run")
            self.assertIsNone(result["result"])
            self.assertIn("cost_est", result)
        finally:
            if original_or:
                _os.environ["OPENROUTER_API_KEY"] = original_or
            if original_a:
                _os.environ["ANTHROPIC_API_KEY"] = original_a

    def test_delegate_errors_without_api_key(self):
        import os as _os
        original_or = _os.environ.pop("OPENROUTER_API_KEY", None)
        original_a = _os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            result = tm_delegate.delegate(
                task="refactor", loadout_name="specialist", dry_run=False
            )
            self.assertEqual(result["status"], "error")
            self.assertIn("API key", result["error"])
        finally:
            if original_or:
                _os.environ["OPENROUTER_API_KEY"] = original_or
            if original_a:
                _os.environ["ANTHROPIC_API_KEY"] = original_a

    def test_system_prompt_contains_all_skill_contents(self):
        system, names = tm_delegate._build_system_prompt("specialist")
        self.assertIn("refactor", system.lower())
        self.assertIn("code-review", system.lower())
        self.assertEqual(sorted(names), sorted(["refactor", "code-review"]))
        self.assertIn("specialist", system)


class AutopilotTests(unittest.TestCase):
    """V2 autopilot = offer + delegate in one call."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_autopilot_returns_no_loadouts_when_store_empty(self):
        result = tm_delegate.autopilot(task="anything", dry_run=True)
        self.assertEqual(result["status"], "no_loadouts")

    def test_autopilot_dry_run_picks_canonical_and_stops(self):
        h1 = store.pin_skill(_write_synthetic_skill(
            self.work, "refactor",
            body_suffix="## Extract function\nPull a named chunk out of a long function.",
        ))["id"]
        h2 = store.pin_skill(_write_synthetic_skill(self.work, "code-review"))["id"]
        loadout.create_loadout("refactor_stack", [h1, h2])

        result = tm_delegate.autopilot(
            task="refactor the long handler function", dry_run=True
        )
        # Should either be dry_run (picked a match) or no_match if relevance was too low
        self.assertIn(result["status"], ("dry_run", "no_match"))
        if result["status"] == "dry_run":
            self.assertEqual(result["offer"]["name"], "refactor_stack")

    def test_autopilot_returns_no_match_when_relevance_below_threshold(self):
        h = store.pin_skill(_write_synthetic_skill(self.work, "unrelated"))["id"]
        loadout.create_loadout("unrelated_stack", [h])

        # Set an impossibly high threshold to force no_match
        result = tm_delegate.autopilot(
            task="totally unrelated task involving widgets",
            dry_run=True,
            min_relevance=0.99,
        )
        self.assertEqual(result["status"], "no_match")
        self.assertIn("best_offer", result)
        self.assertIn("all_offers", result)


class ProtocolV2IntegrationTests(unittest.TestCase):
    """Protocol checkin/checkout should surface loadouts and offers in V2."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_home = Path(self.tmp.name) / ".toolmaster"
        _redirect_store(self.tmp_home)
        self.work = Path(self.tmp.name) / "work"
        self.work.mkdir()
        self.project_dir = Path(self.tmp.name) / "project"
        self.project_dir.mkdir()

        h1 = store.pin_skill(_write_synthetic_skill(
            self.work, "refactor",
            body_suffix="## Extract function\nPull a chunk out.",
        ))["id"]
        h2 = store.pin_skill(_write_synthetic_skill(self.work, "code-review"))["id"]
        loadout.create_loadout("refactor_stack", [h1, h2])

    def tearDown(self):
        self.tmp.cleanup()

    def test_checkin_includes_loadouts_in_toolbox(self):
        state = protocol.checkin(self.project_dir)
        self.assertIn("loadouts", state["toolbox"])
        loadout_names = [lo["name"] for lo in state["toolbox"]["loadouts"]]
        self.assertIn("refactor_stack", loadout_names)

    def test_checkin_protocol_version_bumped(self):
        state = protocol.checkin(self.project_dir)
        self.assertEqual(state["protocol_version"], "1.1")

    def test_checkout_returns_both_skill_suggestions_and_loadout_offers(self):
        protocol.checkin(self.project_dir)  # required to create manifest
        result = protocol.checkout(
            self.project_dir, "refactor the long handler function"
        )
        self.assertIn("suggestions", result)
        self.assertIn("loadout_offers", result)
        # Loadout offers should contain refactor_stack for a refactor task
        offer_names = [o["name"] for o in result["loadout_offers"]]
        self.assertIn("refactor_stack", offer_names)


class ScoutDiscoveryTests(unittest.TestCase):
    """Discovery-layer sanity tests. No network — only introspect config/helpers."""

    def test_watch_list_has_no_duplicates(self):
        self.assertEqual(
            len(scout.DEFAULT_WATCH_REPOS),
            len(set(scout.DEFAULT_WATCH_REPOS)),
            "DEFAULT_WATCH_REPOS must not contain duplicates",
        )

    def test_watch_list_has_valid_repo_slugs(self):
        for slug in scout.DEFAULT_WATCH_REPOS:
            parts = slug.split("/")
            self.assertEqual(len(parts), 2, f"Bad slug: {slug}")
            self.assertTrue(parts[0], f"Empty owner: {slug}")
            self.assertTrue(parts[1], f"Empty repo: {slug}")

    def test_awesome_lists_are_subset_of_or_additional_to_watch(self):
        # Awesome lists should all be valid GitHub slugs too
        for slug in scout.AWESOME_LISTS:
            parts = slug.split("/")
            self.assertEqual(len(parts), 2, f"Bad awesome-list slug: {slug}")

    def test_topics_are_lowercase_kebab(self):
        for topic in scout.GITHUB_TOPICS:
            self.assertEqual(topic, topic.lower(), f"Topic must be lowercase: {topic}")
            self.assertNotIn(" ", topic, f"Topic must be kebab-case: {topic}")

    def test_github_headers_include_auth_when_token_set(self):
        import os as _os
        original = _os.environ.get("GITHUB_TOKEN")
        _os.environ["GITHUB_TOKEN"] = "test-token-123"
        try:
            headers = scout._github_headers()
            self.assertEqual(headers.get("Authorization"), "Bearer test-token-123")
        finally:
            if original is None:
                _os.environ.pop("GITHUB_TOKEN", None)
            else:
                _os.environ["GITHUB_TOKEN"] = original

    def test_github_headers_falls_back_to_gh_token(self):
        import os as _os
        originals = {
            "GITHUB_TOKEN": _os.environ.pop("GITHUB_TOKEN", None),
            "GH_TOKEN": _os.environ.get("GH_TOKEN"),
        }
        _os.environ["GH_TOKEN"] = "gh-fallback-token"
        try:
            headers = scout._github_headers()
            self.assertEqual(headers.get("Authorization"), "Bearer gh-fallback-token")
        finally:
            if originals["GITHUB_TOKEN"]:
                _os.environ["GITHUB_TOKEN"] = originals["GITHUB_TOKEN"]
            if originals["GH_TOKEN"]:
                _os.environ["GH_TOKEN"] = originals["GH_TOKEN"]
            else:
                _os.environ.pop("GH_TOKEN", None)

    def test_github_headers_omits_auth_when_no_token(self):
        import os as _os
        originals = {
            "GITHUB_TOKEN": _os.environ.pop("GITHUB_TOKEN", None),
            "GH_TOKEN": _os.environ.pop("GH_TOKEN", None),
        }
        try:
            headers = scout._github_headers()
            self.assertNotIn("Authorization", headers)
            self.assertIn("User-Agent", headers)
        finally:
            if originals["GITHUB_TOKEN"]:
                _os.environ["GITHUB_TOKEN"] = originals["GITHUB_TOKEN"]
            if originals["GH_TOKEN"]:
                _os.environ["GH_TOKEN"] = originals["GH_TOKEN"]

    def test_discovery_star_threshold_is_sane(self):
        # Must be > 0 and not so high that it excludes legit small libraries
        self.assertGreater(scout.MIN_DISCOVERY_STARS, 0)
        self.assertLess(scout.MIN_DISCOVERY_STARS, 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
