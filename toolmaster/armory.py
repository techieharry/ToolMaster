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


def render(state: dict, width: int = 70) -> str:
    """Render the full armory frame as a string."""
    w = max(width, 50)
    iw = w - 4  # inner width (inside border)
    lines = []

    def border_top():
        lines.append(f"{C.YELLOW}{'╔' + '═' * (w - 2) + '╗'}{C.RESET}")

    def border_bot():
        lines.append(f"{C.YELLOW}{'╚' + '═' * (w - 2) + '╝'}{C.RESET}")

    def border_mid():
        lines.append(f"{C.YELLOW}{'╠' + '═' * (w - 2) + '╣'}{C.RESET}")

    def row(content: str = "", pad: int = 0):
        # Strip ANSI for length calc
        visible = re.sub(r"\033\[[0-9;]*m", "", content)
        padding = max(0, iw - len(visible) - pad)
        lines.append(f"{C.YELLOW}║{C.RESET} {content}{' ' * padding} {C.YELLOW}║{C.RESET}")

    def section_header(title: str):
        visible_len = len(title)
        dashes = iw - visible_len - 4
        left = 1
        right = max(0, dashes - left)
        lines.append(
            f"{C.YELLOW}║{C.RESET} {C.DIM}{'─' * left}{C.RESET} "
            f"{C.BOLD}{C.CYAN}{title}{C.RESET} "
            f"{C.DIM}{'─' * right}{C.RESET} {C.YELLOW}║{C.RESET}"
        )

    # === HEADER ===
    border_top()
    title = f"{C.BOLD}{C.B_YELLOW}  \u2694  T O O L M A S T E R   A R M O R Y  \u2694{C.RESET}"
    cycle_str = f"{C.GRAY}Cycle: {state['scout']['total_cycles']}{C.RESET}"
    row(f"{title}      {cycle_str}")
    border_mid()

    # === STATS BAR ===
    n_skills = len(state["skills"])
    n_pinned = sum(1 for s in state["skills"] if s["type"] == "pinned")
    n_projects = len(state["projects"])
    pid_str = f"{C.B_GREEN}\u25cf{C.RESET}" if state["watcher_pid"] else f"{C.B_RED}\u25cf{C.RESET}"
    stats = (
        f"{pid_str} Familiar  "
        f"{C.B_WHITE}{n_skills}{C.RESET} items  "
        f"{C.B_WHITE}{n_pinned}{C.RESET} pinned  "
        f"{C.B_WHITE}{n_projects}{C.RESET} realms  "
        f"{C.B_WHITE}{state['scout']['audited']}{C.RESET} scouted  "
        f"{C.B_WHITE}{state['scout']['repos']}{C.RESET} lairs"
    )
    row(stats)
    row()

    # === INVENTORY ===
    section_header(f"INVENTORY ({n_skills} items)")
    row()

    for s in state["skills"][:15]:
        icon = get_icon(s["name"])
        name = s["name"][:20].ljust(20)
        bar = health_bar(s["avg_edit"], 10)
        edit_str = f"{s['avg_edit']:>4.0f}%" if s["avg_edit"] is not None else "  -  "
        runs_str = f"{s['runs']}x" if s["runs"] else "  "
        rar_label, rar_color, _ = rarity(s["avg_edit"])
        rar_str = f"{rar_color}{rar_label:<9}{C.RESET}"
        pin = f"{C.B_WHITE}\u25c6{C.RESET}" if s["type"] == "pinned" else f"{C.GRAY}\u25c7{C.RESET}"

        row(f"  {pin} {icon} {C.B_WHITE}{name}{C.RESET} {bar} {edit_str}  {runs_str:>3}  {rar_str}")

    if len(state["skills"]) > 15:
        row(f"  {C.GRAY}... and {len(state['skills']) - 15} more items{C.RESET}")
    row()

    # === SCOUT'S LORE ===
    section_header("SCOUT'S LORE")
    row()

    lore_entries = state["scout_log"][:5]
    if lore_entries:
        for entry in lore_entries:
            lore_text = format_lore(entry["msg"])
            # Word-wrap lore to fit
            words = lore_text.split()
            line_buf = f"  {C.DIM}\"{C.RESET}{C.GRAY}"
            visible_len = 3  # quote + space
            for word in words:
                if visible_len + len(word) + 1 > iw - 4:
                    line_buf += f"{C.RESET}"
                    row(line_buf)
                    line_buf = f"   {C.GRAY}"
                    visible_len = 3
                line_buf += (" " if visible_len > 3 else "") + word
                visible_len += len(word) + 1
            line_buf += f"\"{C.RESET}"
            row(line_buf)
            row()
    else:
        row(f"  {C.DIM}The Scout has not yet ventured forth...{C.RESET}")
        row()

    # === PROPOSALS (LOOT DROPS) ===
    section_header(f"LOOT DROPS ({len(state['proposals'])} proposals)")
    row()

    for p in state["proposals"][:5]:
        safety = p.get("safety", "unknown")
        if safety == "safe":
            icon = f"{C.B_GREEN}\u2705{C.RESET}"
            tag = f"{C.B_GREEN}SAFE{C.RESET}"
        elif safety == "caution":
            icon = f"{C.B_YELLOW}\u26a0\ufe0f{C.RESET}"
            tag = f"{C.B_YELLOW}CURSED{C.RESET}"
        else:
            icon = f"{C.B_RED}\u274c{C.RESET}"
            tag = f"{C.B_RED}REJECT{C.RESET}"

        title = p.get("title", "")[:40]
        ptype = p.get("type", "")
        type_str = f"{C.B_BLUE}import{C.RESET}" if ptype == "import" else f"{C.MAGENTA}{ptype}{C.RESET}"
        row(f"  {icon} {C.B_WHITE}{title}{C.RESET}")
        row(f"     {type_str}  {tag}  {C.GRAY}{p.get('source_repo', '')}{C.RESET}")

    if not state["proposals"]:
        row(f"  {C.DIM}No loot has been discovered yet.{C.RESET}")
    row()

    # === FOOTER ===
    border_mid()
    familiar = "patrolling" if state["watcher_pid"] else "resting"
    row(
        f"  \U0001f43e Familiar (PID {state['watcher_pid'] or '???'}) {familiar}...  "
        f"{state['scout']['audited']} lairs searched  "
        f"{state['total_runs']} quests completed"
    )
    border_bot()

    return "\n".join(lines)


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
