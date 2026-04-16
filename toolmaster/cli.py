"""ToolMaster CLI — content-addressed skill registry and loadout system."""

import argparse
import json
import sys

from . import store, loadout, record, compare, suggest, protocol, scout, quality, offer, delegate as _delegate, viz


def cmd_pin(args):
    """Pin a skill directory into the store."""
    try:
        # Run quality gate first, show report
        report = quality.validate_skill(args.skill_dir)
        print(f"Quality: {report['score']}/100 ({'PASS' if report['status'] == 'pass' else 'FAIL'})")
        if report["critical"]:
            for i in report["critical"]:
                print(f"  {i}")
        if report["high"]:
            for i in report["high"]:
                print(f"  {i}")

        manifest = store.pin_skill(args.skill_dir)
        print(f"Pinned: {manifest['name']}")
        print(f"  Hash: {manifest['id'][:12]}...")
        print(f"  Full: {manifest['id']}")
        print(f"  Files: {len(manifest['files'])}")
        for rel_path in manifest["files"]:
            print(f"    {rel_path}")
    except ValueError as e:
        print(f"Quality gate FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except (NotADirectoryError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_ls(args):
    """List all pinned skills."""
    skills = store.list_skills()
    if not skills:
        print("No pinned skills. Use 'toolmaster pin <skill-dir>' to pin one.")
        return

    print(f"{'ID':<14} {'Name':<30} {'Files':<6} {'Pinned'}")
    print("-" * 70)
    for s in skills:
        pinned = s["pinned_at"][:10]
        print(f"{s['short_id']}  {s['name']:<30} {s['files']:<6} {pinned}")


def cmd_resolve(args):
    """Resolve a pinned skill to a target directory."""
    try:
        path = store.resolve_skill(args.hash, args.target)
        print(f"Resolved to: {path}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_show(args):
    """Show details of a pinned skill."""
    try:
        manifest = store.get_manifest(args.hash)
        print(f"Name:     {manifest['name']}")
        print(f"Hash:     {manifest['id']}")
        print(f"Source:   {manifest.get('source', 'unknown')}")
        print(f"Pinned:   {manifest['pinned_at']}")
        print(f"Files ({len(manifest['files'])}):")
        for rel_path, info in manifest["files"].items():
            print(f"  {rel_path} ({info['size']} bytes, {info['hash'][:12]}...)")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_loadout_create(args):
    """Create a loadout from skill hashes."""
    try:
        lo = loadout.create_loadout(args.name, args.hashes)
        print(f"Loadout '{lo['name']}' created with {len(lo['skills'])} skills:")
        for i, s in enumerate(lo["skills"], 1):
            print(f"  {i}. {s['name']} ({s['hash'][:12]}...)")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_loadout_show(args):
    """Show a loadout."""
    try:
        lo = loadout.get_loadout(args.name)
        print(f"Loadout: {lo['name']}")
        print(f"Created: {lo['created_at']}")
        print(f"Skills ({len(lo['skills'])}, priority order):")
        for i, s in enumerate(lo["skills"], 1):
            print(f"  {i}. {s['name']} ({s['hash'][:12]}...)")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_loadout_list(args):
    """List all loadouts."""
    loadouts = loadout.list_loadouts()
    if not loadouts:
        print("No loadouts. Use 'toolmaster loadout create <name> <hash1> <hash2> ...'")
        return

    for lo in loadouts:
        print(f"{lo['name']}: {', '.join(lo['skill_names'])} ({lo['skills']} skills)")


def cmd_loadout_apply(args):
    """Apply a loadout to agent skill paths."""
    try:
        path = loadout.apply_loadout(args.name, args.target)
        print(f"Applied loadout '{args.name}' to {path}")
        print(f"Lock file: {path.parent / 'toolmaster.lock'}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_loadout_diff(args):
    """Diff two loadouts."""
    try:
        diff = loadout.diff_loadouts(args.a, args.b)

        only_a_key = f"only_in_{args.a}"
        only_b_key = f"only_in_{args.b}"

        if diff[only_a_key]:
            print(f"\nOnly in '{args.a}':")
            for h, n in diff[only_a_key].items():
                print(f"  - {n} ({h[:12]}...)")

        if diff[only_b_key]:
            print(f"\nOnly in '{args.b}':")
            for h, n in diff[only_b_key].items():
                print(f"  + {n} ({h[:12]}...)")

        if diff["shared"]:
            print(f"\nShared ({len(diff['shared'])} skills):")
            for h, n in diff["shared"].items():
                print(f"  = {n}")

        if diff["order_changes"]:
            print(f"\nPriority changes:")
            for c in diff["order_changes"]:
                print(f"  {c['name']}: #{c[f'priority_in_{args.a}']} → #{c[f'priority_in_{args.b}']}")

        if not any([diff[only_a_key], diff[only_b_key], diff["order_changes"]]):
            print("Loadouts are identical.")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_record(args):
    """Quick-record a task."""
    try:
        rec = record.quick_record(
            task=args.task,
            output=args.output or "",
            loadout_name=args.loadout,
            rating=args.rating,
        )
        print(f"Recorded: {rec['id']}")
        print(f"  Task: {rec['task'][:80]}")
        if rec["loadout"]:
            print(f"  Loadout: {rec['loadout']}")
        if rec["rating"]:
            print(f"  Rating: {rec['rating']}/5")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_record_list(args):
    """List all recordings."""
    recordings = record.list_recordings(loadout=args.loadout)
    if not recordings:
        print("No recordings. Use 'toolmaster record -t \"task description\"'")
        return

    print(f"{'ID':<14} {'Status':<10} {'Loadout':<16} {'Task'}")
    print("-" * 70)
    for r in recordings:
        task = r["task"][:35] + "..." if len(r["task"]) > 35 else r["task"]
        lo = r.get("loadout") or "-"
        rating = f" [{r['rating']}/5]" if r.get("rating") else ""
        print(f"{r['id']}  {r['status']:<10} {lo:<16} {task}{rating}")


def cmd_compare(args):
    """Compare two loadouts against recorded tasks."""
    try:
        use_llm = not args.heuristic

        # Cost preview before burning tokens
        if use_llm and not args.no_cost_preview:
            est = compare.estimate_compare_cost(args.a, args.b)
            if "error" not in est:
                print(f"\nEstimated cost: {est['task_count']} tasks × "
                      f"({est['est_input_tokens']} in + {est['est_output_tokens']} out) tokens "
                      f"= ~${est['est_usd']} via {est['model']}")
                print("(Results are cached by (loadout-pair, recording-set); re-runs are free.)\n")

        result = compare.compare_loadouts(args.a, args.b, use_llm=use_llm,
                                           use_cache=not args.no_cache)

        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        cache_tag = " (from cache)" if result.get("from_cache") else ""
        print(f"\n{'='*60}")
        print(f"  LOADOUT COMPARISON: {result['loadout_a']} vs {result['loadout_b']}")
        print(f"  Method: {result['method']}{cache_tag}")
        print(f"{'='*60}")
        print(f"\n  Tasks evaluated: {result['tasks_evaluated']}")
        print(f"  {result['loadout_a']}: {result['wins_a']} wins")
        print(f"  {result['loadout_b']}: {result['wins_b']} wins")
        print(f"  Ties: {result['ties']}")
        print(f"\n  WINNER: {result['winner'].upper()}")

        if result["details"]:
            print(f"\n{'─'*60}")
            print("  Per-task breakdown:")
            for d in result["details"]:
                conf = f" ({d['confidence']:.0%})" if d.get("confidence") else ""
                print(f"\n  [{d['winner']}{conf}] {d['task']}")
                if d.get("reasoning"):
                    print(f"    → {d['reasoning']}")

        print()
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_suggest(args):
    """Suggest relevant skills from the global store."""
    try:
        if args.proven:
            # Show proven skills only
            proven = suggest.get_proven_skills(
                min_uses=args.min_uses or 3,
                max_edit_distance=args.max_edit or 30.0,
            )
            if not proven:
                print("No proven skills yet. Need more usage data.")
                return
            print(f"\n{'='*60}")
            print(f"  PROVEN SKILLS (used {args.min_uses or 3}+ times, <{args.max_edit or 30}% edit)")
            print(f"{'='*60}\n")
            for s in proven:
                projects = ", ".join(s["projects"]) if s["projects"] else "—"
                print(f"  {s['name']}")
                print(f"    Hash: {s['hash']}  Used: {s['times_used']}x  Edit: {s['avg_edit_distance']}%")
                print(f"    Projects: {projects}")
                print()
        else:
            results = suggest.suggest(
                args.task,
                top_n=args.top or 5,
                use_llm=not args.heuristic,
            )
            if not results:
                print("No skills in the store. Pin some first.")
                return
            print(f"\n{'='*60}")
            print(f"  SUGGESTED SKILLS for: \"{args.task[:60]}\"")
            print(f"  Method: {results[0].get('match_method', '?')}")
            print(f"{'='*60}\n")
            for i, s in enumerate(results, 1):
                perf = s["performance"]
                used = perf["times_used"]
                edit = f"{perf['avg_edit_distance']}%" if perf['avg_edit_distance'] is not None else "no data"
                projects = ", ".join(perf["projects_used_in"]) if perf["projects_used_in"] else "—"

                print(f"  {i}. {s['name']} ({s['short_hash']})")
                print(f"     {s['description'][:100]}")
                print(f"     Used: {used}x | Edit: {edit} | Projects: {projects}")
                print(f"     Score: {s.get('relevance_score', '?')}")
                print()

            print(f"  Use: toolmaster loadout create <name> <hash1> <hash2> ...")
            print(f"  Or:  toolmaster resolve <hash> <target-dir>\n")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_delegate(args):
    """Skill dispatch — delegate a task to a specialist agent with a pinned loadout."""
    try:
        est = _delegate.estimate_delegate_cost(args.loadout, args.task, args.model)
        if "error" in est:
            print(f"Error: {est['error']}", file=sys.stderr)
            sys.exit(1)

        print(f"\nDelegation preview")
        print(f"  loadout:      {est['loadout']} ({est['skill_count']} skills)")
        print(f"  model:        {est['model']}")
        print(f"  est tokens:   {est['est_input_tokens']} in / {est['est_output_tokens']} out")
        print(f"  est cost:     ~${est['est_usd']}")
        task_preview = args.task[:80] + ("..." if len(args.task) > 80 else "")
        print(f"  task:         {task_preview}")

        if args.dry_run:
            print("\n[dry-run] No API call made. Pass without --dry-run to execute.\n")
            return

        if not args.yes:
            reply = input("\nProceed? [y/N]: ").strip().lower()
            if reply not in ("y", "yes"):
                print("Aborted.")
                return

        print("\nDelegating...\n")
        result = _delegate.delegate(
            task=args.task,
            loadout_name=args.loadout,
            model=args.model,
            dry_run=False,
            record=not args.no_record,
        )

        if result["status"] == "error":
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        print(f"{'='*64}")
        print(f"  RESULT (via {result['model']}, loadout={result['loadout']})")
        print(f"{'='*64}\n")
        print(result["result"])
        print()
        if result.get("recording_id"):
            print(f"Recording: {result['recording_id']}")
        print()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_viz(args):
    """Generate interactive HTML visualization of the skill portfolio."""
    try:
        out = viz.generate_viz(output_path=args.output)
        print(f"Visualization generated: {out.resolve()}")
        print(f"Open in browser: file:///{out.resolve().as_posix()}")
        if not args.no_open:
            import webbrowser
            webbrowser.open(str(out.resolve()))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_autopilot(args):
    """V2: offer + delegate in one call. The autonomous verb."""
    try:
        result = _delegate.autopilot(
            task=args.task,
            model=args.model,
            dry_run=args.dry_run,
            min_relevance=args.min_relevance,
        )

        if result["status"] == "no_loadouts":
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        if result["status"] == "no_match":
            print(f"\n{result['message']}\n")
            print(f"Best offer was: {result['best_offer']['name']} (relevance {result['best_offer']['relevance']})")
            return
        if result["status"] == "error":
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

        offer_info = result.get("offer", {})
        print(f"\n{'='*64}")
        print(f"  AUTOPILOT — offer engine picked: {offer_info.get('name', '?')}")
        print(f"  relevance: {offer_info.get('relevance', '?')}  "
              f"cold_start: {offer_info.get('cold_start', '?')}")
        print(f"  reason: {offer_info.get('reason', '')[:80]}")
        print(f"{'='*64}\n")

        if result.get("status") == "dry_run":
            print(f"[dry-run] Would delegate to '{offer_info.get('name')}' for ~${result['cost_est']['est_usd']}")
            return

        print(f"Model: {result.get('model')}")
        print(f"Recording: {result.get('recording_id')}")
        print()
        print(result.get("result", ""))
        print()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_offer(args):
    """V2 offer engine — return 3 loadout offers for a task."""
    try:
        offers = offer.suggest_loadouts(args.task, top_n=args.top or 3)
        if not offers:
            print("No loadouts in the store. Create one with 'toolmaster loadout create <name> <hash1>...'")
            return

        mode = "cold-start" if offers[0].get("cold_start") else "warm (outcome-weighted)"
        print(f"\n{'='*64}")
        print(f"  LOADOUT OFFERS for: \"{args.task[:55]}\"")
        print(f"  Mode: {mode}")
        print(f"{'='*64}\n")

        labels = {
            "canonical": "[1] CANONICAL   - top-ranked loadout",
            "iterated":  "[2] ITERATED    - canonical's refined cousin",
            "sideways":  "[3] SIDEWAYS    - compositionally different option",
        }

        for i, o in enumerate(offers, 1):
            label = labels.get(o["type"], f"[{i}] {o['type'].upper()}")
            print(label)
            print(f"    name:      {o['name']}")
            print(f"    skills:    {', '.join(o['skills'])}")
            print(f"    relevance: {o['relevance']}")
            print(f"    why:       {o['reason']}")
            if "iterated_note" in o:
                print(f"    tweak:     {o['iterated_note']}")
            print()

        print("Pick one with: toolmaster loadout apply <name> --target <agent>")
        print("Your choice will be logged and feed future offer rankings.\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_checkin(args):
    """Protocol: check in at session start."""
    import os
    project_dir = args.project or os.getcwd()
    state = protocol.checkin(project_dir)
    proven = state["toolbox"]["proven"]
    print(f"Checked in: {state['project']}")
    print(f"Toolbox: {state['toolbox']['total_skills']} skills")
    if proven:
        print(f"Proven tools ({len(proven)}):")
        for p in proven[:5]:
            print(f"  {p['name']} ({p['hash'][:12]}) — {p['used']}x, {p['edit']}% edit")
    if state["proposals"]:
        print(f"Proposals ({len(state['proposals'])}):")
        for prop in state["proposals"][:3]:
            print(f"  {prop}")
    print(f"\nSession manifest: {project_dir}/data/toolmaster_session.json")


def cmd_checkout_tool(args):
    """Protocol: check for existing tools before building."""
    import os
    project_dir = args.project or os.getcwd()
    result = protocol.checkout(project_dir, args.task)
    if result["suggestions"]:
        print(f"Found {len(result['suggestions'])} relevant tools:\n")
        for i, s in enumerate(result["suggestions"], 1):
            edit = f"{s['edit_distance']}%" if s['edit_distance'] is not None else "no data"
            print(f"  {i}. {s['name']} ({s['hash']}) — used {s['times_used']}x, edit {edit}")
            print(f"     {s['description']}")
            print()
        print("Use: toolmaster resolve <hash> ./skills/")
        print("Then: toolmaster used <skill-name> <hash> --task \"...\"")
    else:
        print("No relevant tools found. Build from scratch and it'll be added to the toolbox.")


def cmd_used(args):
    """Protocol: report using a tool."""
    import os
    project_dir = args.project or os.getcwd()
    entry = protocol.log_tool_used(project_dir, args.skill, args.hash, args.task, args.outcome)
    print(f"Logged: used {entry['skill']} ({entry['outcome']})")


def cmd_created(args):
    """Protocol: report creating a new tool."""
    import os
    project_dir = args.project or os.getcwd()
    entry = protocol.log_tool_created(project_dir, args.skill_dir, args.task, args.reason)
    print(f"Logged + pinned: created {entry['skill']} ({entry['hash'][:12] if entry['hash'] else '?'})")


def cmd_forked(args):
    """Protocol: report forking/improving a tool."""
    import os
    project_dir = args.project or os.getcwd()
    entry = protocol.log_tool_forked(project_dir, args.skill_dir, args.parent_hash, args.task, args.changes)
    print(f"Logged + pinned: forked {entry['skill']} from {entry['parent_hash'][:12]}")
    print(f"  New hash: {entry['new_hash'][:12] if entry['new_hash'] else '?'}")
    print(f"  Changes: {entry['changes']}")


def cmd_return(args):
    """Protocol: end session, return tools to toolbox."""
    import os
    project_dir = args.project or os.getcwd()
    summary = protocol.return_tools(project_dir)
    print(f"\nSession summary for {summary['project']}:")
    print(f"  Tools checked:  {summary['tools_checked']}")
    print(f"  Tools used:     {summary['tools_used']}")
    print(f"  Tools created:  {summary['tools_created']}")
    print(f"  Tools forked:   {summary['tools_forked']}")
    print(f"  Compliance:     {summary['checked_before_building']:.0%}")
    print(f"\nSession archived to data/sessions/")


def cmd_scout(args):
    """Run a scout cycle — search GitHub, audit, re-engineer, propose."""
    result = scout.scout_cycle()
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    print(f"\nScout cycle complete:")
    print(f"  Repos searched:    {result['repos_searched']}")
    print(f"  Skills found:      {result['skills_found']}")
    print(f"  Skills audited:    {result['skills_audited']}")
    print(f"  Re-engineered:     {result['reengineered']}")
    print(f"  Proposals created: {result['proposals_created']}")
    print(f"  Tokens used:       ~{result['tokens_used']}")
    print(f"\nProposals at: ~/.toolmaster/proposals/")
    print(f"Scout log at: ~/.toolmaster/scout.log")


def cmd_watch(args):
    """Global watcher — monitor all projects for logs."""
    from . import global_watcher
    if args.status:
        # Inject --status into sys.argv for global_watcher.main()
        import sys
        sys.argv = ["toolmaster-watcher", "--status"]
        global_watcher.main()
    elif args.once:
        results = global_watcher.poll_once()
        print(f"Processed {len(results)} logs" if results else "No new logs")
    else:
        try:
            global_watcher.poll_loop(args.interval)
        except KeyboardInterrupt:
            print("\nWatcher stopped.")


def main():
    parser = argparse.ArgumentParser(
        prog="toolmaster",
        description="Content-addressed skill registry and loadout system",
    )
    sub = parser.add_subparsers(dest="command")

    # pin
    p_pin = sub.add_parser("pin", help="Pin a skill directory")
    p_pin.add_argument("skill_dir", help="Path to skill directory containing SKILL.md")

    # ls
    sub.add_parser("ls", help="List pinned skills")

    # resolve
    p_resolve = sub.add_parser("resolve", help="Resolve a pinned skill to a directory")
    p_resolve.add_argument("hash", help="Manifest hash (or prefix)")
    p_resolve.add_argument("target", help="Target directory")

    # show
    p_show = sub.add_parser("show", help="Show details of a pinned skill")
    p_show.add_argument("hash", help="Manifest hash (or prefix)")

    # loadout
    p_lo = sub.add_parser("loadout", help="Manage loadouts")
    lo_sub = p_lo.add_subparsers(dest="loadout_command")

    p_lo_create = lo_sub.add_parser("create", help="Create a loadout")
    p_lo_create.add_argument("name", help="Loadout name")
    p_lo_create.add_argument("hashes", nargs="+", help="Skill hashes in priority order")

    p_lo_show = lo_sub.add_parser("show", help="Show a loadout")
    p_lo_show.add_argument("name", help="Loadout name")

    lo_sub.add_parser("list", help="List all loadouts")

    p_lo_apply = lo_sub.add_parser("apply", help="Apply a loadout to agent paths")
    p_lo_apply.add_argument("name", help="Loadout name")
    p_lo_apply.add_argument("--target", default="claude",
                            choices=sorted(loadout.AGENT_TARGETS.keys()),
                            help="Target agent system (default: claude)")

    p_lo_diff = lo_sub.add_parser("diff", help="Diff two loadouts")
    p_lo_diff.add_argument("a", help="First loadout name")
    p_lo_diff.add_argument("b", help="Second loadout name")

    # record
    p_rec = sub.add_parser("record", help="Record a task")
    p_rec.add_argument("-t", "--task", required=True, help="Task description")
    p_rec.add_argument("-o", "--output", help="Task output/result")
    p_rec.add_argument("-l", "--loadout", help="Loadout used")
    p_rec.add_argument("-r", "--rating", type=int, choices=[1, 2, 3, 4, 5], help="Rating 1-5")

    # record list
    p_rec_ls = sub.add_parser("recordings", help="List recordings")
    p_rec_ls.add_argument("-l", "--loadout", help="Filter by loadout name")

    # compare
    p_cmp = sub.add_parser("compare", help="Compare two loadouts")
    p_cmp.add_argument("a", help="First loadout name")
    p_cmp.add_argument("b", help="Second loadout name")
    p_cmp.add_argument("--heuristic", action="store_true", help="Use heuristic instead of LLM")
    p_cmp.add_argument("--no-cache", action="store_true", help="Skip cache, force re-judge")
    p_cmp.add_argument("--no-cost-preview", action="store_true", help="Suppress pre-run cost estimate")

    # viz
    p_viz = sub.add_parser("viz", help="Generate interactive HTML skill portfolio visualization")
    p_viz.add_argument("-o", "--output", default="toolmaster-viz.html", help="Output path (default: toolmaster-viz.html)")
    p_viz.add_argument("--no-open", action="store_true", help="Don't auto-open in browser")

    # offer (V2)
    p_off = sub.add_parser("offer", help="V2: return 3 loadout offers for a task")
    p_off.add_argument("task", help="Task description")
    p_off.add_argument("--top", type=int, default=3, help="Number of offers (default: 3)")

    # delegate (V2 skill dispatch primitive)
    p_del = sub.add_parser("delegate", help="Delegate a task to a specialist agent with a loadout")
    p_del.add_argument("task", help="Task description for the specialist")
    p_del.add_argument("--loadout", required=True, help="Loadout name to dispatch with")
    p_del.add_argument("--model", help="Override model (default: TOOLMASTER_MODEL or haiku-4.5)")
    p_del.add_argument("--dry-run", action="store_true", help="Show cost estimate without calling")
    p_del.add_argument("--no-record", action="store_true", help="Skip writing a recording")
    p_del.add_argument("-y", "--yes", action="store_true", help="Skip the confirmation prompt")

    # autopilot (V2 one-shot: offer + delegate)
    p_auto = sub.add_parser("autopilot", help="V2: offer + delegate in one call (autonomous verb)")
    p_auto.add_argument("task", help="Task description")
    p_auto.add_argument("--model", help="Override model (default: TOOLMASTER_MODEL or haiku-4.5)")
    p_auto.add_argument("--dry-run", action="store_true", help="Show cost estimate without calling")
    p_auto.add_argument("--min-relevance", type=float, default=0.05,
                        help="Min offer relevance to auto-delegate (default: 0.05)")
    p_auto.add_argument("-y", "--yes", action="store_true", help="(reserved — autopilot is always non-interactive)")

    # suggest
    p_sug = sub.add_parser("suggest", help="Suggest skills for a task")
    p_sug.add_argument("task", nargs="?", help="Task description")
    p_sug.add_argument("--proven", action="store_true", help="Show proven skills only")
    p_sug.add_argument("--top", type=int, default=5, help="Number of suggestions")
    p_sug.add_argument("--heuristic", action="store_true", help="Use heuristic ranking")
    p_sug.add_argument("--min-uses", type=int, help="Min uses for proven (default: 3)")
    p_sug.add_argument("--max-edit", type=float, help="Max edit distance for proven (default: 30)")

    # === PROTOCOL COMMANDS ===
    # checkin
    p_ci = sub.add_parser("checkin", help="Protocol: start session, get toolbox state")
    p_ci.add_argument("--project", help="Project directory (default: cwd)")

    # checkout (check for existing tools)
    p_co = sub.add_parser("checkout", help="Protocol: check for tools before building")
    p_co.add_argument("task", help="What you need to do")
    p_co.add_argument("--project", help="Project directory (default: cwd)")

    # used
    p_used = sub.add_parser("used", help="Protocol: report using a toolbox tool")
    p_used.add_argument("skill", help="Skill name")
    p_used.add_argument("hash", help="Skill hash")
    p_used.add_argument("--task", required=True, help="What task it was used for")
    p_used.add_argument("--outcome", default="used_as_is",
                        choices=["used_as_is", "modified_slightly", "heavily_modified", "rejected"])
    p_used.add_argument("--project", help="Project directory (default: cwd)")

    # created
    p_new = sub.add_parser("created", help="Protocol: report creating a new tool")
    p_new.add_argument("skill_dir", help="Path to new skill directory")
    p_new.add_argument("--task", required=True, help="What task prompted creation")
    p_new.add_argument("--reason", default="no_existing_tool",
                       choices=["no_existing_tool", "existing_too_generic", "completely_new_domain"])
    p_new.add_argument("--project", help="Project directory (default: cwd)")

    # forked
    p_fork = sub.add_parser("forked", help="Protocol: report forking/improving a tool")
    p_fork.add_argument("skill_dir", help="Path to forked skill directory")
    p_fork.add_argument("parent_hash", help="Hash of the parent skill")
    p_fork.add_argument("--task", required=True, help="What task prompted the fork")
    p_fork.add_argument("--changes", default="", help="What was changed")
    p_fork.add_argument("--project", help="Project directory (default: cwd)")

    # return
    p_ret = sub.add_parser("return", help="Protocol: end session, return tools")
    p_ret.add_argument("--project", help="Project directory (default: cwd)")

    # scout
    sub.add_parser("scout", help="Scout GitHub for skills, audit, re-engineer, propose")

    # watch
    p_watch = sub.add_parser("watch", help="Global watcher — monitor all projects")
    p_watch.add_argument("--once", action="store_true", help="Run one cycle and exit")
    p_watch.add_argument("--interval", type=int, default=60, help="Poll interval seconds")
    p_watch.add_argument("--status", action="store_true", help="Show current insights")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    dispatch = {
        "pin": cmd_pin,
        "ls": cmd_ls,
        "resolve": cmd_resolve,
        "show": cmd_show,
        "record": cmd_record,
        "recordings": cmd_record_list,
        "compare": cmd_compare,
        "viz": cmd_viz,
        "offer": cmd_offer,
        "delegate": cmd_delegate,
        "autopilot": cmd_autopilot,
        "suggest": cmd_suggest,
        "scout": cmd_scout,
        "checkin": cmd_checkin,
        "checkout": cmd_checkout_tool,
        "used": cmd_used,
        "created": cmd_created,
        "forked": cmd_forked,
        "return": cmd_return,
        "watch": cmd_watch,
    }

    if args.command == "loadout":
        lo_dispatch = {
            "create": cmd_loadout_create,
            "show": cmd_loadout_show,
            "list": cmd_loadout_list,
            "apply": cmd_loadout_apply,
            "diff": cmd_loadout_diff,
        }
        if args.loadout_command is None:
            p_lo.print_help()
            return
        lo_dispatch[args.loadout_command](args)
    else:
        dispatch[args.command](args)


if __name__ == "__main__":
    main()
