"""Live dashboard server — zero-dependency localhost HTTP server.

Serves a tabbed HTML dashboard that polls ~/.toolmaster/ state files
every 5 seconds via fetch(). Three tabs:

  Graph     — D3 force-directed skill portfolio (same as toolmaster viz)
  Research  — live scout.log feed, repo scan status, harvest activity
  Proposals — all proposals with safety filtering and detail expansion

Usage:
    toolmaster live                    # starts on http://localhost:8484
    toolmaster live --port 9090        # custom port

Uses only stdlib (http.server, json, pathlib). No external dependencies.
"""

from __future__ import annotations

import json
import os
import re
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .store import TOOLMASTER_HOME, list_skills


def start_server(port: int = 8484, open_browser: bool = True):
    """Start the live dashboard HTTP server."""
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://localhost:{port}"
    print(f"ToolMaster Live Dashboard")
    print(f"  URL:   {url}")
    print(f"  State: {TOOLMASTER_HOME}")
    print(f"  Press Ctrl+C to stop\n")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        server.server_close()


class DashboardHandler(BaseHTTPRequestHandler):
    """Handles / (HTML page) and /api/state (JSON state refresh)."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_html()
        elif parsed.path == "/api/state":
            self._serve_state()
        else:
            self.send_error(404)

    def _serve_html(self):
        html = _build_dashboard_html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _serve_state(self):
        state = _collect_live_state()
        body = json.dumps(state, default=str)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default access logging — too noisy with 5s polling."""
        pass


def _collect_live_state() -> dict:
    """Read all ~/.toolmaster/ state files fresh for each poll."""

    # Global insights
    insights = {}
    gi_path = TOOLMASTER_HOME / "global_insights.json"
    if gi_path.exists():
        try:
            insights = json.loads(gi_path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass

    # Skills in store
    try:
        skills = list_skills()
    except Exception:
        skills = []

    skill_perf = insights.get("skill_performance", {})

    skill_list = []
    for s in skills:
        perf = skill_perf.get(s["name"], {})
        edits = perf.get("edit_distances", [])
        avg_edit = round(sum(edits) / len(edits), 1) if edits else None
        skill_list.append({
            "name": s["name"],
            "type": "pinned",
            "hash": s["short_id"],
            "runs": perf.get("runs", 0),
            "avg_edit": avg_edit,
            "rejections": perf.get("rejections", 0),
        })

    # Also add tracked skills not in store
    for sk_name, sp in skill_perf.items():
        if not any(s["name"] == sk_name for s in skill_list):
            edits = sp.get("edit_distances", [])
            avg_edit = round(sum(edits) / len(edits), 1) if edits else None
            skill_list.append({
                "name": sk_name,
                "type": "tracked",
                "hash": "",
                "runs": sp.get("runs", 0),
                "avg_edit": avg_edit,
                "rejections": sp.get("rejections", 0),
            })

    # Projects
    project_health = insights.get("project_health", {})

    # Scout log (last 50 lines, reverse chronological)
    scout_log = []
    scout_log_path = TOOLMASTER_HOME / "scout.log"
    if scout_log_path.exists():
        try:
            lines = scout_log_path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
            for line in reversed(lines[-100:]):
                # Parse [timestamp] message
                m = re.match(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)", line)
                if m:
                    scout_log.append({"ts": m.group(1), "msg": m.group(2)})
            scout_log = scout_log[:50]
        except Exception:
            pass

    # Watcher log (last 30 lines)
    watcher_log = []
    watcher_log_path = TOOLMASTER_HOME / "watcher.log"
    if watcher_log_path.exists():
        try:
            lines = watcher_log_path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
            for line in reversed(lines[-60:]):
                line = line.strip()
                if line and not line.startswith("Press Ctrl"):
                    watcher_log.append(line)
            watcher_log = watcher_log[:30]
        except Exception:
            pass

    # Scout state
    scout_summary = {"total_cycles": 0, "audited_skills": 0, "known_repos": 0,
                     "recent_repos": [], "recent_audits": []}
    ss_path = TOOLMASTER_HOME / "scout_state.json"
    if ss_path.exists():
        try:
            ss = json.loads(ss_path.read_text(encoding="utf-8", errors="replace"))
            all_repos = ss.get("known_repos", [])
            all_audited = ss.get("audited_skills", [])
            scout_summary = {
                "total_cycles": ss.get("total_cycles", 0),
                "audited_skills": len(all_audited),
                "known_repos": len(all_repos),
                "recent_repos": all_repos[-20:] if all_repos else [],
                "recent_audits": all_audited[-20:] if all_audited else [],
            }
        except Exception:
            pass

    # Proposals (all)
    proposals = []
    proposals_dir = TOOLMASTER_HOME / "proposals"
    if proposals_dir.exists():
        for pf in sorted(proposals_dir.glob("*.json"), reverse=True):
            try:
                p = json.loads(pf.read_text(encoding="utf-8", errors="replace"))
                proposals.append({
                    "id": p.get("id", pf.stem),
                    "type": p.get("type", "unknown"),
                    "title": p.get("title", ""),
                    "description": p.get("description", ""),
                    "source_repo": p.get("source_repo", ""),
                    "source_url": p.get("source_url", ""),
                    "safety": p.get("safety", "unknown"),
                    "status": p.get("status", "pending"),
                    "created_at": p.get("created_at", ""),
                    "overlaps_with": p.get("overlaps_with", []),
                })
            except Exception:
                continue

    # Project-skill links (from recordings + log files)
    graph_links = []
    link_pairs = set()
    rec_dir = TOOLMASTER_HOME / "recordings"
    if rec_dir.exists():
        for rf in rec_dir.glob("*.json"):
            try:
                rec = json.loads(rf.read_text(encoding="utf-8", errors="replace"))
                task = rec.get("task", "")
                if task.startswith("["):
                    bracket_end = task.find("]")
                    if bracket_end > 0:
                        proj = task[1:bracket_end].replace("delegate", "").strip()
                        if " — " in task or " -- " in task:
                            sep = " — " if " — " in task else " -- "
                            skills_part = task.split(sep, 1)[-1].strip()
                            for sk in skills_part.split(","):
                                sk = sk.strip().split("(")[0].strip()
                                if sk and len(sk) < 50:
                                    pair = (proj, sk)
                                    if pair not in link_pairs:
                                        link_pairs.add(pair)
                                        graph_links.append({
                                            "source": f"project:{proj}",
                                            "target": f"skill:{sk}",
                                        })
            except Exception:
                continue

    # Also scan project logs for deliverables_generated
    claude_dir = Path(os.environ.get("CLAUDE_DIR", "C:/Claude"))
    if claude_dir.is_dir():
        for proj_dir in claude_dir.iterdir():
            if not proj_dir.is_dir() or proj_dir.name == "ToolMaster":
                continue
            logs_dir = proj_dir / "data" / "logs"
            if not logs_dir.exists():
                continue
            for lf in logs_dir.glob("*.json"):
                try:
                    log = json.loads(lf.read_text(encoding="utf-8", errors="replace"))
                    proj = proj_dir.name
                    for sk in log.get("deliverables_generated", []):
                        pair = (proj, sk)
                        if pair not in link_pairs:
                            link_pairs.add(pair)
                            graph_links.append({
                                "source": f"project:{proj}",
                                "target": f"skill:{sk}",
                            })
                except Exception:
                    continue

    # Watcher PID
    watcher_pid = None
    pid_path = TOOLMASTER_HOME / "watcher.pid"
    if pid_path.exists():
        try:
            watcher_pid = int(pid_path.read_text().strip())
        except Exception:
            pass

    # Recordings count
    rec_count = 0
    rec_dir = TOOLMASTER_HOME / "recordings"
    if rec_dir.exists():
        rec_count = len(list(rec_dir.glob("*.json")))

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "watcher_pid": watcher_pid,
        "skills": skill_list,
        "projects": project_health,
        "scout_summary": scout_summary,
        "scout_log": scout_log,
        "watcher_log": watcher_log,
        "proposals": proposals,
        "recordings_count": rec_count,
        "total_runs": insights.get("total_runs", 0),
        "graph_links": graph_links,
    }


def _build_dashboard_html() -> str:
    """Build the full tabbed dashboard HTML with polling JS."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ToolMaster Live Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #0d1117; color: #c9d1d9;
}

/* Top bar */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    background: #161b22; border-bottom: 1px solid #30363d;
    padding: 10px 20px; height: 50px;
}
.topbar h1 { font-size: 16px; color: #f0f6fc; }
.topbar .status { font-size: 12px; color: #8b949e; }
.topbar .status .live { color: #3fb950; }

/* Tabs */
.tabs {
    display: flex; background: #161b22;
    border-bottom: 1px solid #30363d; padding: 0 20px;
}
.tab {
    padding: 10px 20px; font-size: 13px; color: #8b949e;
    cursor: pointer; border-bottom: 2px solid transparent;
    transition: all 0.15s;
}
.tab:hover { color: #c9d1d9; }
.tab.active { color: #f0f6fc; border-bottom-color: #f78166; }

/* Tab content */
.tab-content { display: none; padding: 20px; height: calc(100vh - 95px); overflow-y: auto; }
.tab-content.active { display: block; }

/* Stats row */
.stats-row {
    display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap;
}
.stat-card {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 14px 18px; min-width: 140px; flex: 1;
}
.stat-card .value { font-size: 28px; font-weight: 700; color: #f0f6fc; }
.stat-card .label { font-size: 11px; color: #8b949e; margin-top: 4px; }

/* Research feed */
.feed { max-width: 900px; }
.feed-section { margin-bottom: 24px; }
.feed-title {
    font-size: 13px; font-weight: 600; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 1px solid #21262d;
}
.feed-entry {
    display: flex; gap: 12px; padding: 8px 12px;
    border-radius: 6px; margin-bottom: 3px; font-size: 13px;
    transition: background 0.1s;
}
.feed-entry:hover { background: #161b22; }
.feed-ts { color: #484f58; font-size: 11px; white-space: nowrap; min-width: 140px; }
.feed-msg { color: #c9d1d9; word-break: break-word; }
.feed-msg .audit { color: #3fb950; }
.feed-msg .caution { color: #d29922; }
.feed-msg .reject { color: #f85149; }
.feed-msg .search { color: #58a6ff; }
.feed-msg .harvest { color: #a371f7; }

/* Repo chips */
.repo-chips {
    display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;
}
.repo-chip {
    background: #21262d; border: 1px solid #30363d; border-radius: 12px;
    padding: 4px 10px; font-size: 11px; color: #8b949e;
}
.repo-chip a { color: #58a6ff; text-decoration: none; }
.repo-chip a:hover { text-decoration: underline; }

/* Proposals */
.proposals-grid { max-width: 1000px; }
.proposal-filters {
    display: flex; gap: 8px; margin-bottom: 16px;
}
.filter-btn {
    padding: 6px 14px; border-radius: 20px; font-size: 12px;
    border: 1px solid #30363d; background: #21262d; color: #8b949e;
    cursor: pointer; transition: all 0.15s;
}
.filter-btn:hover, .filter-btn.active { background: #30363d; color: #f0f6fc; }
.filter-btn.safe.active { border-color: #3fb950; color: #3fb950; }
.filter-btn.caution.active { border-color: #d29922; color: #d29922; }
.filter-btn.import.active { border-color: #58a6ff; color: #58a6ff; }

.proposal-card {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 14px 18px; margin-bottom: 10px;
    border-left: 4px solid #30363d;
    transition: all 0.15s; cursor: pointer;
}
.proposal-card:hover { border-color: #484f58; }
.proposal-card.safe { border-left-color: #3fb950; }
.proposal-card.caution { border-left-color: #d29922; }
.proposal-card.unsafe { border-left-color: #f85149; }
.proposal-card .title { font-weight: 600; color: #f0f6fc; font-size: 14px; margin-bottom: 4px; }
.proposal-card .desc { color: #8b949e; font-size: 12px; margin-bottom: 6px; }
.proposal-card .meta { color: #484f58; font-size: 11px; }
.proposal-card .meta a { color: #58a6ff; text-decoration: none; }
.proposal-card .meta a:hover { text-decoration: underline; }
.proposal-card .badges { display: flex; gap: 6px; margin-top: 6px; }
.badge {
    font-size: 10px; padding: 2px 8px; border-radius: 10px;
    border: 1px solid #30363d; color: #8b949e;
}
.badge.safe { border-color: #238636; color: #3fb950; }
.badge.caution { border-color: #9e6a03; color: #d29922; }
.badge.unsafe { border-color: #da3633; color: #f85149; }
.badge.import { border-color: #1f6feb; color: #58a6ff; }
.badge.extract { border-color: #6e40c9; color: #a371f7; }

/* Health bar */
.health-bar {
    display: flex; height: 6px; border-radius: 3px;
    overflow: hidden; background: #21262d; margin: 8px 0;
}
.hb-green { background: #3fb950; }
.hb-yellow { background: #d29922; }
.hb-red { background: #f85149; }

/* Skills table */
.skills-table { width: 100%; max-width: 900px; border-collapse: collapse; }
.skills-table th {
    text-align: left; font-size: 11px; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.5px;
    padding: 8px 12px; border-bottom: 1px solid #21262d;
}
.skills-table td {
    padding: 8px 12px; font-size: 13px; border-bottom: 1px solid #161b22;
}
.skills-table tr:hover td { background: #161b22; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; }

/* Graph node labels */
.node-label {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 10px; fill: #8b949e;
    text-anchor: middle; pointer-events: none;
    paint-order: stroke;
    stroke: #0d1117; stroke-width: 3px; stroke-linejoin: round;
}
.node-label.project { font-size: 12px; font-weight: 600; fill: #e6edf3; }
.node-label.hidden { display: none; }

/* Graph tooltip */
.tooltip {
    position: fixed; pointer-events: none;
    background: #1c2128; border: 1px solid #30363d;
    border-radius: 6px; padding: 10px 14px;
    font-size: 12px; line-height: 1.5;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    z-index: 1000; display: none;
    max-width: 320px;
}
.tooltip .tooltip-name { font-weight: 600; color: #f0f6fc; font-size: 14px; }
.tooltip .tooltip-meta { color: #8b949e; margin-top: 2px; }

.empty-state {
    text-align: center; color: #484f58; padding: 40px;
    font-size: 14px;
}
</style>
</head>
<body>

<div class="topbar">
    <h1>ToolMaster Live Dashboard</h1>
    <div class="status">
        <span class="live" id="status-dot">&#9679;</span>
        <span id="status-text">Connecting...</span>
    </div>
</div>

<div class="tabs">
    <div class="tab active" onclick="switchTab('graph')">Graph</div>
    <div class="tab" onclick="switchTab('research')">Research</div>
    <div class="tab" onclick="switchTab('proposals')">Proposals</div>
    <div class="tab" onclick="switchTab('skills')">Skills</div>
</div>

<!-- GRAPH TAB -->
<div id="tab-graph" class="tab-content active" style="padding:0; height:calc(100vh - 95px); position:relative; overflow:hidden;">
    <div id="graph-tooltip" class="tooltip"></div>
    <svg id="graph-svg" style="width:100%; height:100%;"></svg>
    <div style="position:absolute; bottom:12px; left:12px; font-size:11px; color:#484f58;">
        Drag nodes to rearrange. Scroll to zoom. Hover for details.
    </div>
</div>

<!-- RESEARCH TAB -->
<div id="tab-research" class="tab-content">
    <div class="stats-row" id="stats-row"></div>
    <div class="feed">
        <div class="feed-section">
            <div class="feed-title">Scout Activity (live)</div>
            <div id="scout-feed"></div>
        </div>
        <div class="feed-section">
            <div class="feed-title">Watcher Activity</div>
            <div id="watcher-feed"></div>
        </div>
        <div class="feed-section">
            <div class="feed-title">Recently Discovered Repos (<span id="repo-count">0</span>)</div>
            <div class="repo-chips" id="repo-chips"></div>
        </div>
    </div>
</div>

<!-- PROPOSALS TAB -->
<div id="tab-proposals" class="tab-content">
    <div class="proposal-filters" id="proposal-filters">
        <div class="filter-btn active" data-filter="all" onclick="filterProposals('all', this)">All</div>
        <div class="filter-btn import" data-filter="import" onclick="filterProposals('import', this)">Import</div>
        <div class="filter-btn safe" data-filter="safe" onclick="filterProposals('safe', this)">Safe</div>
        <div class="filter-btn caution" data-filter="caution" onclick="filterProposals('caution', this)">Caution</div>
    </div>
    <div id="proposals-list"></div>
</div>

<!-- SKILLS TAB -->
<div id="tab-skills" class="tab-content">
    <div class="feed-title">Skill Health Overview</div>
    <div class="health-bar" id="skill-health-bar"></div>
    <table class="skills-table" id="skills-table">
        <thead>
            <tr><th>Skill</th><th>Status</th><th>Runs</th><th>Edit Distance</th><th>Rejections</th><th>Health</th></tr>
        </thead>
        <tbody id="skills-tbody"></tbody>
    </table>
</div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
let currentFilter = 'all';
let latestState = null;
let graphBuilt = false;

function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', t.getAttribute('onclick').includes("'" + name + "'"));
    });
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
}

function filterProposals(filter, btn) {
    currentFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderProposals(latestState.proposals);
}

function colorForEdit(edit) {
    if (edit === null || edit === undefined) return '#484f58';
    if (edit <= 20) return '#3fb950';
    if (edit <= 50) return '#d29922';
    return '#f85149';
}

function healthLabel(edit) {
    if (edit === null || edit === undefined) return 'No data';
    if (edit <= 20) return 'Healthy';
    if (edit <= 50) return 'Moderate';
    return 'Weak';
}

function colorScoutMsg(msg) {
    if (msg.includes('Audited') && !msg.includes('CAUTION') && !msg.includes('REJECTED'))
        return msg.replace(/(Audited .+?:)/, '<span class="audit">$1</span>');
    if (msg.includes('CAUTION'))
        return '<span class="caution">' + msg + '</span>';
    if (msg.includes('REJECTED') || msg.includes('reject'))
        return '<span class="reject">' + msg + '</span>';
    if (msg.includes('Found') || msg.includes('Topic') || msg.includes('search'))
        return '<span class="search">' + msg + '</span>';
    if (msg.includes('HARVEST') || msg.includes('Pinned'))
        return '<span class="harvest">' + msg + '</span>';
    return msg;
}

function renderStats(state) {
    const s = state;
    document.getElementById('stats-row').innerHTML = `
        <div class="stat-card"><div class="value">${s.skills.length}</div><div class="label">Skills</div></div>
        <div class="stat-card"><div class="value">${Object.keys(s.projects).length}</div><div class="label">Projects</div></div>
        <div class="stat-card"><div class="value">${s.scout_summary.audited_skills}</div><div class="label">Audited</div></div>
        <div class="stat-card"><div class="value">${s.proposals.length}</div><div class="label">Proposals</div></div>
        <div class="stat-card"><div class="value">${s.scout_summary.known_repos}</div><div class="label">Repos</div></div>
        <div class="stat-card"><div class="value">${s.scout_summary.total_cycles}</div><div class="label">Scout Cycles</div></div>
        <div class="stat-card"><div class="value">${s.recordings_count}</div><div class="label">Recordings</div></div>
        <div class="stat-card"><div class="value">${s.total_runs}</div><div class="label">Total Runs</div></div>
    `;
}

function renderScoutFeed(log) {
    if (!log.length) {
        document.getElementById('scout-feed').innerHTML = '<div class="empty-state">No scout activity yet. Start the watcher daemon.</div>';
        return;
    }
    document.getElementById('scout-feed').innerHTML = log.map(e =>
        `<div class="feed-entry"><span class="feed-ts">${e.ts}</span><span class="feed-msg">${colorScoutMsg(e.msg)}</span></div>`
    ).join('');
}

function renderWatcherFeed(log) {
    if (!log.length) {
        document.getElementById('watcher-feed').innerHTML = '<div class="empty-state">No watcher activity yet.</div>';
        return;
    }
    document.getElementById('watcher-feed').innerHTML = log.slice(0, 20).map(line =>
        `<div class="feed-entry"><span class="feed-msg">${line}</span></div>`
    ).join('');
}

function renderRepos(repos) {
    document.getElementById('repo-count').textContent = repos.length;
    document.getElementById('repo-chips').innerHTML = repos.map(r =>
        `<span class="repo-chip"><a href="https://github.com/${r}" target="_blank">${r}</a></span>`
    ).join('');
}

function renderProposals(proposals) {
    let filtered = proposals;
    if (currentFilter !== 'all') {
        filtered = proposals.filter(p => p.safety === currentFilter || p.type === currentFilter);
    }
    if (!filtered.length) {
        document.getElementById('proposals-list').innerHTML = '<div class="empty-state">No proposals match this filter.</div>';
        return;
    }
    document.getElementById('proposals-list').innerHTML = filtered.map(p => {
        const safetyClass = ['safe','caution','unsafe'].includes(p.safety) ? p.safety : '';
        const typeClass = ['import','extract_techniques'].includes(p.type) ? p.type.split('_')[0] : '';
        return `<div class="proposal-card ${safetyClass}">
            <div class="title">${p.title}</div>
            <div class="desc">${p.description || ''}</div>
            <div class="meta">
                ${p.source_repo ? `<a href="https://github.com/${p.source_repo}" target="_blank">${p.source_repo}</a>` : ''}
                ${p.source_url ? ` &middot; <a href="${p.source_url}" target="_blank">View source</a>` : ''}
                ${p.created_at ? ` &middot; ${p.created_at.slice(0, 10)}` : ''}
            </div>
            <div class="badges">
                <span class="badge ${safetyClass}">${p.safety}</span>
                <span class="badge ${typeClass}">${p.type}</span>
                <span class="badge">${p.status}</span>
            </div>
        </div>`;
    }).join('');
}

function renderSkills(skills) {
    const sorted = [...skills].sort((a, b) => (b.runs || 0) - (a.runs || 0));
    const healthy = sorted.filter(s => s.avg_edit !== null && s.avg_edit <= 20).length;
    const moderate = sorted.filter(s => s.avg_edit !== null && s.avg_edit > 20 && s.avg_edit <= 50).length;
    const weak = sorted.filter(s => s.avg_edit !== null && s.avg_edit > 50).length;
    const total = sorted.length || 1;

    document.getElementById('skill-health-bar').innerHTML =
        `<div class="hb-green" style="width:${Math.max(1, healthy/total*100)}%"></div>` +
        `<div class="hb-yellow" style="width:${Math.max(0, moderate/total*100)}%"></div>` +
        `<div class="hb-red" style="width:${Math.max(0, weak/total*100)}%"></div>`;

    document.getElementById('skills-tbody').innerHTML = sorted.map(s => {
        const color = colorForEdit(s.avg_edit);
        const editStr = s.avg_edit !== null ? s.avg_edit + '%' : '-';
        return `<tr>
            <td><span class="dot" style="background:${color}"></span>${s.name}</td>
            <td>${s.type}</td>
            <td>${s.runs || 0}</td>
            <td>${editStr}</td>
            <td>${s.rejections || 0}</td>
            <td style="color:${color}">${healthLabel(s.avg_edit)}</td>
        </tr>`;
    }).join('');
}

// --- Graph rendering ---

function buildGraph(state) {
    if (graphBuilt) return; // only build once, not on every poll
    graphBuilt = true;

    const svgEl = document.getElementById('graph-svg');
    const svg = d3.select('#graph-svg');
    svg.selectAll('*').remove();
    const container = svg.append('g');
    const rect = svgEl.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    // Build nodes from skills + projects
    const nodes = [];
    const nodeIds = new Set();
    (state.skills || []).forEach(s => {
        const id = 'skill:' + s.name;
        nodes.push({ id, name: s.name, type: s.type, runs: s.runs, avg_edit: s.avg_edit, rejections: s.rejections, hash: s.hash });
        nodeIds.add(id);
    });
    Object.keys(state.projects || {}).forEach(proj => {
        const id = 'project:' + proj;
        const h = state.projects[proj];
        nodes.push({ id, name: proj, type: 'project', runs: h.runs || 0, avg_edit: h.avg_edit_distance, avg_rating: h.avg_rating });
        nodeIds.add(id);
    });

    // Links from state (project -> skill, built from recordings + log files)
    const rawLinks = state.graph_links || [];
    const validLinks = rawLinks.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target));

    // Build adjacency for hover-highlight
    const adjacency = new Map();
    nodes.forEach(n => adjacency.set(n.id, new Set()));
    validLinks.forEach(l => { adjacency.get(l.source).add(l.target); adjacency.get(l.target).add(l.source); });

    // Zoom
    const zoom = d3.zoom().scaleExtent([0.15, 5]).on('zoom', e => container.attr('transform', e.transform));
    svg.call(zoom);

    function nodeColor(d) {
        if (d.type === 'project') return '#58a6ff';
        if (d.avg_edit === null || d.avg_edit === undefined) return '#484f58';
        if (d.avg_edit <= 20) return '#3fb950';
        if (d.avg_edit <= 50) return '#d29922';
        return '#f85149';
    }

    function nodeRadius(d) {
        if (d.type === 'project') return 22;
        return Math.min(7 + Math.sqrt(d.runs || 0) * 3.5, 24);
    }

    function truncName(name) {
        return name.length > 18 ? name.slice(0, 17) + '\u2026' : name;
    }

    function showLabel(d) {
        if (d.type === 'project') return true;
        if (d.type === 'pinned') return true;
        if ((d.runs || 0) >= 2) return true;
        return false;
    }

    // Simulation — tuned for 30-50 nodes in a tabbed panel
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(validLinks).id(d => d.id).distance(160).strength(0.3))
        .force('charge', d3.forceManyBody().strength(-500))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 35).strength(0.8))
        .force('x', d3.forceX(width / 2).strength(0.04))
        .force('y', d3.forceY(height / 2).strength(0.04));

    // Draw links
    const link = container.append('g')
        .selectAll('line').data(validLinks).join('line')
        .attr('stroke', '#30363d').attr('stroke-width', 1.5).attr('stroke-opacity', 0.5);

    // Node groups
    const node = container.append('g')
        .selectAll('g').data(nodes).join('g')
        .style('cursor', 'pointer')
        .call(d3.drag()
            .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
            .on('end', (e, d) => { if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
        );

    // Project rects
    node.filter(d => d.type === 'project').append('rect')
        .attr('width', 44).attr('height', 28).attr('x', -22).attr('y', -14)
        .attr('rx', 6).attr('ry', 6)
        .attr('fill', nodeColor).attr('stroke', '#1f6feb').attr('stroke-width', 2);

    // Skill circles
    node.filter(d => d.type !== 'project').append('circle')
        .attr('r', nodeRadius).attr('fill', nodeColor)
        .attr('stroke', '#30363d').attr('stroke-width', 1.5)
        .attr('stroke-dasharray', d => d.type === 'tracked' ? '4,3' : 'none');

    // Labels
    node.append('text')
        .text(d => truncName(d.name))
        .attr('class', d => 'node-label' + (d.type === 'project' ? ' project' : '') + (showLabel(d) ? '' : ' hidden'))
        .attr('dy', d => d.type === 'project' ? 26 : nodeRadius(d) + 16);

    // Tooltip
    const tooltip = d3.select('#graph-tooltip');
    node.on('mouseover', function(e, d) {
        let html = '<div class="tooltip-name">' + d.name + '</div>';
        if (d.type === 'project') {
            html += '<div class="tooltip-meta">Project &middot; ' + (d.runs||0) + ' runs';
            if (d.avg_edit != null) html += ' &middot; ' + d.avg_edit + '% edit';
            if (d.avg_rating != null) html += ' &middot; Rating: ' + d.avg_rating + '/5';
            html += '</div>';
        } else {
            html += '<div class="tooltip-meta">' + (d.type === 'pinned' ? 'Pinned' : 'Tracked') + '</div>';
            html += '<div class="tooltip-meta">' + (d.runs||0) + ' runs';
            if (d.avg_edit != null) html += ' &middot; ' + d.avg_edit + '% edit';
            if (d.rejections) html += ' &middot; ' + d.rejections + ' rejections';
            html += '</div>';
        }
        tooltip.html(html).style('display', 'block');
        // Highlight node + neighbors
        const neighbors = adjacency.get(d.id) || new Set();
        node.style('opacity', n => (n.id === d.id || neighbors.has(n.id)) ? 1 : 0.15);
        link.style('stroke-opacity', l => (l.source.id === d.id || l.target.id === d.id) ? 0.8 : 0.05)
            .style('stroke-width', l => (l.source.id === d.id || l.target.id === d.id) ? 2.5 : 1);
        node.selectAll('text').each(function(n) {
            d3.select(this).classed('hidden', !(n.id === d.id || neighbors.has(n.id)));
        });
    }).on('mousemove', function(e) {
        let left = e.clientX + 14, top = e.clientY - 10;
        const tw = 280;
        if (left + tw > window.innerWidth - 10) left = e.clientX - tw - 14;
        if (top + 100 > window.innerHeight) top = window.innerHeight - 110;
        tooltip.style('left', left + 'px').style('top', top + 'px');
    }).on('mouseout', function() {
        tooltip.style('display', 'none');
        node.style('opacity', 1);
        link.style('stroke-opacity', 0.5).style('stroke-width', 1.5);
        node.selectAll('text').each(function(d) { d3.select(this).classed('hidden', !showLabel(d)); });
    });

    // Tick
    simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
    });

    // Zoom to fit after settling
    simulation.on('end', () => {
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        nodes.forEach(n => {
            const r = nodeRadius(n) + 30;
            if (n.x - r < minX) minX = n.x - r;
            if (n.y - r < minY) minY = n.y - r;
            if (n.x + r > maxX) maxX = n.x + r;
            if (n.y + r > maxY) maxY = n.y + r;
        });
        const bw = maxX - minX, bh = maxY - minY;
        const scale = Math.min(width / bw, height / bh) * 0.85;
        const tx = width / 2 - (minX + bw / 2) * scale;
        const ty = height / 2 - (minY + bh / 2) * scale;
        svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    });
}

// --- Polling ---

async function poll() {
    try {
        const resp = await fetch('/api/state');
        const state = await resp.json();
        latestState = state;

        // Status
        const pid = state.watcher_pid;
        document.getElementById('status-text').textContent =
            `Watcher PID: ${pid || 'not running'} | Last update: ${state.timestamp}`;
        document.getElementById('status-dot').style.color = pid ? '#3fb950' : '#f85149';

        buildGraph(state);
        renderStats(state);
        renderScoutFeed(state.scout_log);
        renderWatcherFeed(state.watcher_log);
        renderRepos(state.scout_summary.recent_repos);
        renderProposals(state.proposals);
        renderSkills(state.skills);
    } catch (err) {
        document.getElementById('status-text').textContent = 'Connection lost: ' + err.message;
        document.getElementById('status-dot').style.color = '#f85149';
    }
}

// Initial load + 5-second polling
poll();
setInterval(poll, 5000);
</script>
</body>
</html>"""
