"""The Armory — RPG-themed terminal UI for ToolMaster.

Pure ANSI escape codes + Unicode box-drawing + emoji. Zero dependencies.
Reads ~/.toolmaster/ state files and renders a live-updating retro RPG
inventory screen directly in the terminal.

Usage:
    toolmaster armory              # live-updating, 5s refresh
    toolmaster armory --once       # single render and exit

Item rarity by edit distance:
    LEGENDARY  0%       (output used as-is every time)
    EPIC       1-10%
    RARE       11-25%
    UNCOMMON   26-50%
    COMMON     no data
    BROKEN     50%+     (needs re-forging)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from .store import TOOLMASTER_HOME, list_skills


# ANSI color codes
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    # Foreground
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GRAY    = "\033[90m"
    B_RED   = "\033[91m"
    B_GREEN = "\033[92m"
    B_YELLOW= "\033[93m"
    B_BLUE  = "\033[94m"
    B_MAGENTA="\033[95m"
    B_CYAN  = "\033[96m"
    B_WHITE = "\033[97m"


# Rarity tiers
def rarity(edit: float | None) -> tuple[str, str, str]:
    """Returns (label, color, bar_color) for an edit distance value."""
    if edit is None:
        return ("COMMON", C.GRAY, C.GRAY)
    if edit == 0:
        return ("LEGENDARY", C.B_MAGENTA, C.B_MAGENTA)
    if edit <= 10:
        return ("EPIC", C.MAGENTA, C.MAGENTA)
    if edit <= 25:
        return ("RARE", C.B_BLUE, C.B_BLUE)
    if edit <= 50:
        return ("UNCOMMON", C.B_GREEN, C.GREEN)
    return ("BROKEN", C.B_RED, C.RED)


# Tool icons by name patterns
TOOL_ICONS = {
    "refactor": "\U0001f527",      # wrench
    "bug": "\U0001f5e1\ufe0f",     # dagger
    "fix": "\U0001f5e1\ufe0f",     # dagger
    "test": "\U0001f6e1\ufe0f",    # shield
    "review": "\U0001f441\ufe0f",  # eye
    "code": "\U0001f4dc",          # scroll
    "deploy": "\U0001f680",        # rocket
    "security": "\U0001f512",      # lock
    "strategy": "\U0001fa84",      # wand
    "marketing": "\U0001fa84",     # wand
    "social": "\U0001f4e2",        # megaphone
    "document": "\U0001f4d6",      # book
    "data": "\U0001f52e",          # crystal ball
    "api": "\U000026a1",           # lightning
    "scraper": "\U0001f578\ufe0f", # spider web
    "voice": "\U0001f3a4",         # microphone
    "skill": "\U00002728",         # sparkles
    "classify": "\U0001f3af",      # target
    "quota": "\U0001f4b0",         # money bag
    "question": "\U00002753",      # question mark
}


def get_icon(name: str) -> str:
    """Pick an icon for a skill name based on keyword matching."""
    name_lower = name.lower()
    for keyword, icon in TOOL_ICONS.items():
        if keyword in name_lower:
            return icon
    return "\U00002699\ufe0f"  # gear (default)


def health_bar(edit: float | None, width: int = 12) -> str:
    """Render a colored progress bar for edit distance."""
    _, _, bar_color = rarity(edit)
    if edit is None:
        return f"{C.GRAY}{'.' * width}{C.RESET}"
    filled = max(0, round((100 - edit) / 100 * width))
    empty = width - filled
    return f"{bar_color}{'█' * filled}{C.GRAY}{'░' * empty}{C.RESET}"


def star_rating(edit: float | None) -> str:
    """Convert edit distance to star rating."""
    if edit is None:
        return f"{C.GRAY}☆☆☆☆☆{C.RESET}"
    if edit == 0:
        stars = 5
    elif edit <= 10:
        stars = 4
    elif edit <= 25:
        stars = 3
    elif edit <= 50:
        stars = 2
    else:
        stars = 1
    _, color, _ = rarity(edit)
    return f"{color}{'★' * stars}{'☆' * (5 - stars)}{C.RESET}"


# Lore formatter
LORE_TEMPLATES = {
    "Audited": (
        'The Scout inspected a {skill} scroll from the {repo} archives. '
        'Verdict: {verdict}.'
    ),
    "CAUTION": (
        'A {skill} artifact from {repo} radiates unstable magic. '
        'The Scout extracts techniques only — too dangerous to import whole.'
    ),
    "REJECTED": (
        'A cursed {skill} was found in the {repo} catacombs. '
        'The Scout rejected it — dark enchantments detected.'
    ),
    "Found": (
        'The Scout discovered {detail} in the wilderness.'
    ),
    "Pinned": (
        'A new {detail} has been forged and added to the Armory.'
    ),
    "HARVEST": (
        'The Familiar harvested {detail} from the project realms.'
    ),
    "Cycle": (
        'The Scout completed a patrol. {detail}'
    ),
    "SYNC": (
        'The Armory synced its records across {detail} project outposts.'
    ),
}


def format_lore(msg: str) -> str:
    """Convert a scout/watcher log message into RPG lore text."""
    # Try to extract skill name and repo
    skill = "an unknown artifact"
    repo = "a distant realm"
    verdict = "unclear"

    m = re.search(r"Audited (\S+) from (\S+): (\S+)", msg)
    if m:
        skill, repo, verdict = m.group(1), m.group(2), m.group(3)
        repo = repo.split("/")[0] if "/" in repo else repo

    if "REJECTED" in msg or "reject" in msg.lower():
        m2 = re.search(r"(\S+) from (\S+)", msg)
        if m2:
            skill, repo = m2.group(1), m2.group(2).split("/")[0]
        return LORE_TEMPLATES["REJECTED"].format(skill=skill, repo=repo)

    if "CAUTION" in msg:
        m2 = re.search(r"(\S+) from (\S+)", msg)
        if m2:
            skill, repo = m2.group(1), m2.group(2).split("/")[0]
        return LORE_TEMPLATES["CAUTION"].format(skill=skill, repo=repo)

    if "Audited" in msg and m:
        return LORE_TEMPLATES["Audited"].format(skill=skill, repo=repo, verdict=verdict)

    if "Found" in msg:
        return LORE_TEMPLATES["Found"].format(detail=msg.split("Found", 1)[-1].strip())

    if "Pinned" in msg or "pinned" in msg:
        return LORE_TEMPLATES["Pinned"].format(detail=msg.split("Pinned", 1)[-1].strip()[:60])

    if "HARVEST" in msg:
        return LORE_TEMPLATES["HARVEST"].format(detail=msg.replace("[HARVEST]", "").strip()[:60])

    if "SYNC" in msg:
        return LORE_TEMPLATES["SYNC"].format(detail=msg.replace("[SYNC]", "").strip()[:50])

    if "Cycle" in msg or "cycle" in msg:
        return LORE_TEMPLATES["Cycle"].format(detail=msg.strip()[:60])

    # Fallback: return as-is but trimmed
    return msg[:80]


def collect_state() -> dict:
    """Read all ~/.toolmaster/ state for the armory display."""
    insights = {}
    gi = TOOLMASTER_HOME / "global_insights.json"
    if gi.exists():
        try:
            insights = json.loads(gi.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass

    # Skills
    try:
        store_skills = list_skills()
    except Exception:
        store_skills = []

    skill_perf = insights.get("skill_performance", {})
    skills = []
    for s in store_skills:
        perf = skill_perf.get(s["name"], {})
        edits = perf.get("edit_distances", [])
        avg_edit = round(sum(edits) / len(edits), 1) if edits else None
        skills.append({
            "name": s["name"],
            "type": "pinned",
            "runs": perf.get("runs", 0),
            "avg_edit": avg_edit,
            "rejections": perf.get("rejections", 0),
        })

    for sk, sp in skill_perf.items():
        if not any(s["name"] == sk for s in skills):
            edits = sp.get("edit_distances", [])
            avg_edit = round(sum(edits) / len(edits), 1) if edits else None
            skills.append({
                "name": sk,
                "type": "tracked",
                "runs": sp.get("runs", 0),
                "avg_edit": avg_edit,
                "rejections": sp.get("rejections", 0),
            })

    # Scout log
    scout_log = []
    sl = TOOLMASTER_HOME / "scout.log"
    if sl.exists():
        try:
            lines = sl.read_text(encoding="utf-8", errors="replace").strip().split("\n")
            for line in reversed(lines[-50:]):
                m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)", line)
                if m:
                    scout_log.append({"ts": m.group(1), "msg": m.group(2)})
            scout_log = scout_log[:10]
        except Exception:
            pass

    # Proposals
    proposals = []
    pd = TOOLMASTER_HOME / "proposals"
    if pd.exists():
        for pf in sorted(pd.glob("*.json"), reverse=True)[:8]:
            try:
                p = json.loads(pf.read_text(encoding="utf-8", errors="replace"))
                proposals.append(p)
            except Exception:
                continue

    # Scout state
    scout = {"total_cycles": 0, "audited": 0, "repos": 0}
    ss = TOOLMASTER_HOME / "scout_state.json"
    if ss.exists():
        try:
            sd = json.loads(ss.read_text(encoding="utf-8", errors="replace"))
            scout = {
                "total_cycles": sd.get("total_cycles", 0),
                "audited": len(sd.get("audited_skills", [])),
                "repos": len(sd.get("known_repos", [])),
            }
        except Exception:
            pass

    # Watcher PID
    pid = None
    pf = TOOLMASTER_HOME / "watcher.pid"
    if pf.exists():
        try:
            pid = int(pf.read_text().strip())
        except Exception:
            pass

    # Projects
    projects = insights.get("project_health", {})

    return {
        "skills": sorted(skills, key=lambda x: (-(x["runs"] or 0), x["name"])),
        "scout_log": scout_log,
        "proposals": proposals,
        "scout": scout,
        "projects": projects,
        "watcher_pid": pid,
        "total_runs": insights.get("total_runs", 0),
    }


def render(state: dict, width: int = 76) -> str:
    """Render a lean, aesthetic armory frame."""
    W = max(min(width, 80), 56)  # clamp 56-80
    IW = W - 4  # usable inner width

    out: list[str] = []
    Y = C.YELLOW  # border color
    R = C.RESET

    def top():
        out.append(f"{Y}\u2554{'═' * (W - 2)}\u2557{R}")

    def bot():
        out.append(f"{Y}\u255a{'═' * (W - 2)}\u255d{R}")

    def sep(label: str = ""):
        if label:
            pad = W - 6 - len(label)
            out.append(f"{Y}\u2560\u2550\u2550 {C.BOLD}{C.CYAN}{label}{R}{Y} {'═' * max(pad, 1)}\u2563{R}")
        else:
            out.append(f"{Y}\u2560{'═' * (W - 2)}\u2563{R}")

    def row(text: str = ""):
        vis = re.sub(r"\033\[[0-9;]*m", "", text)
        pad = IW - len(vis)
        out.append(f"{Y}\u2551{R} {text}{' ' * max(pad, 0)} {Y}\u2551{R}")

    def blank():
        row()

    # Count stats
    n_total = len(state["skills"])
    n_pinned = sum(1 for s in state["skills"] if s["type"] == "pinned")
    n_projs = len(state["projects"])
    familiar_ok = bool(state["watcher_pid"])

    # ── HEADER ──
    top()
    blank()
    title = f"{C.BOLD}{C.B_YELLOW}\u2694  TOOLMASTER ARMORY{R}"
    fam = f"{C.B_GREEN}\u25cf{R}" if familiar_ok else f"{C.B_RED}\u25cb{R}"
    row(f"   {title}                       {fam} {C.GRAY}Cycle {state['scout']['total_cycles']}{R}")
    blank()
    row(
        f"   {C.B_WHITE}{n_total}{R}{C.GRAY} items{R}   "
        f"{C.B_WHITE}{n_pinned}{R}{C.GRAY} pinned{R}   "
        f"{C.B_WHITE}{state['scout']['audited']}{R}{C.GRAY} scouted{R}   "
        f"{C.B_WHITE}{n_projs}{R}{C.GRAY} realms{R}"
    )
    blank()

    # ── INVENTORY ──
    sep("INVENTORY")
    blank()

    shown = state["skills"][:8]
    for s in shown:
        icon = get_icon(s["name"])
        pin = f"{C.B_WHITE}\u25c6{R}" if s["type"] == "pinned" else f"{C.GRAY}\u25c7{R}"
        name = s["name"][:18].ljust(18)
        bar = health_bar(s["avg_edit"], 10)
        edit_s = f"{s['avg_edit']:>3.0f}%" if s["avg_edit"] is not None else "  - "
        runs_s = f"{s['runs']:>2}x" if s["runs"] else "   "
        rl, rc, _ = rarity(s["avg_edit"])
        rar = f"{rc}{rl:<9}{R}"
        row(f"   {pin} {icon} {C.B_WHITE}{name}{R}  {bar} {edit_s} {runs_s}  {rar}")

    rest = n_total - len(shown)
    if rest > 0:
        row(f"   {C.GRAY}+{rest} more{R}")
    blank()

    # ── LORE ──
    sep("SCOUT'S LORE")
    blank()

    lore_items = state["scout_log"][:3]
    if lore_items:
        for entry in lore_items:
            lore = format_lore(entry["msg"])
            _wrap_lore(lore, IW - 6, row)
            blank()
    else:
        row(f"   {C.DIM}The Scout has not yet ventured forth...{R}")
        blank()

    # ── LOOT ──
    n_props = len(state["proposals"])
    sep(f"LOOT DROPS ({n_props})")
    blank()

    for p in state["proposals"][:3]:
        safety = p.get("safety", "unknown")
        if safety == "safe":
            si, st = f"{C.B_GREEN}\u2713{R}", f"{C.B_GREEN}SAFE{R}"
        elif safety == "caution":
            si, st = f"{C.B_YELLOW}!{R}", f"{C.B_YELLOW}CURSED{R}"
        else:
            si, st = f"{C.B_RED}x{R}", f"{C.B_RED}REJECT{R}"
        title_text = p.get("title", "")[:36].ljust(36)
        repo = p.get("source_repo", "")[:20]
        row(f"   {si} {C.B_WHITE}{title_text}{R}  {st}  {C.GRAY}{repo}{R}")

    if not state["proposals"]:
        row(f"   {C.DIM}No loot discovered yet.{R}")
    blank()

    # ── FOOTER ──
    sep()
    pid_s = state["watcher_pid"] or "---"
    fam_s = "patrolling" if familiar_ok else "resting"
    row(f"   \U0001f43e {C.GRAY}Familiar ({pid_s}) {fam_s}{R}     "
        f"{C.GRAY}{state['scout']['audited']} lairs   {state['total_runs']} quests{R}")
    bot()

    return "\n".join(out)


def _wrap_lore(text: str, max_w: int, row_fn):
    """Word-wrap a lore string into bordered rows."""
    words = text.split()
    buf = ""
    cur_len = 0
    first = True
    for word in words:
        if cur_len + len(word) + 1 > max_w:
            prefix = f'   {C.DIM}"{C.RESET}' if first else f"    "
            row_fn(f"{prefix}{C.GRAY}{buf}{C.RESET}")
            buf = ""
            cur_len = 0
            first = False
        buf += (" " if buf else "") + word
        cur_len += len(word) + 1
    if buf:
        prefix = f'   {C.DIM}"{C.RESET}' if first else f"    "
        suffix = f'{C.DIM}"{C.RESET}'
        row_fn(f"{prefix}{C.GRAY}{buf}{suffix}")


def clear_screen():
    """Clear terminal screen (cross-platform)."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def run_armory(once: bool = False, interval: int = 5):
    """Main loop: clear screen, render, sleep, repeat."""
    try:
        # Force UTF-8 output on Windows
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass

        while True:
            state = collect_state()
            term_width = shutil.get_terminal_size((80, 24)).columns
            width = min(term_width, 90)
            frame = render(state, width=width)

            clear_screen()
            print(frame)
            print(f"\n  {C.DIM}Refreshing every {interval}s. Press Ctrl+C to exit.{C.RESET}")

            if once:
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n{C.GRAY}The Armory doors close behind you...{C.RESET}")
