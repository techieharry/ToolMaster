"""Interactive HTML visualization of the ToolMaster skill portfolio.

Reads ~/.toolmaster/ state files and generates a self-contained HTML file
with a D3.js force-directed graph + sidebar stats. No server, no npm,
no build step. Open the output file in any browser.

Usage:
    python -m toolmaster viz                    # writes toolmaster-viz.html
    python -m toolmaster viz -o dashboard.html  # custom output path
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime

from .store import TOOLMASTER_HOME, list_skills, get_manifest, read_blob


def generate_viz(output_path: str = "toolmaster-viz.html") -> Path:
    """Generate the interactive HTML visualization.

    Returns the path to the generated file.
    """
    data = _collect_data()
    html = _render_html(data)
    out = Path(output_path)
    out.write_text(html, encoding="utf-8")
    return out


def _collect_data() -> dict:
    """Read all ~/.toolmaster/ state into a single dict for the template."""

    # Global insights
    insights_path = TOOLMASTER_HOME / "global_insights.json"
    insights = {}
    if insights_path.exists():
        insights = json.loads(insights_path.read_text(encoding="utf-8", errors="replace"))

    # Skills in store
    skills = list_skills()
    skill_perf = insights.get("skill_performance", {})

    skill_nodes = []
    for s in skills:
        perf = skill_perf.get(s["name"], {})
        edits = perf.get("edit_distances", [])
        avg_edit = sum(edits) / len(edits) if edits else None
        skill_nodes.append({
            "id": f"skill:{s['name']}",
            "name": s["name"],
            "type": "skill",
            "hash": s["short_id"],
            "runs": perf.get("runs", 0),
            "avg_edit": round(avg_edit, 1) if avg_edit is not None else None,
            "rejections": perf.get("rejections", 0),
            "pinned_at": s["pinned_at"][:10],
        })

    # Also add tracked skills not yet in the store (from watcher signals)
    for sk_name, sp in skill_perf.items():
        if not any(n["name"] == sk_name for n in skill_nodes):
            edits = sp.get("edit_distances", [])
            avg_edit = sum(edits) / len(edits) if edits else None
            skill_nodes.append({
                "id": f"skill:{sk_name}",
                "name": sk_name,
                "type": "tracked",
                "hash": "",
                "runs": sp.get("runs", 0),
                "avg_edit": round(avg_edit, 1) if avg_edit is not None else None,
                "rejections": sp.get("rejections", 0),
                "pinned_at": "",
            })

    # Projects
    project_health = insights.get("project_health", {})
    project_nodes = []
    for proj_name, health in project_health.items():
        project_nodes.append({
            "id": f"project:{proj_name}",
            "name": proj_name,
            "type": "project",
            "runs": health.get("runs", 0),
            "avg_edit": health.get("avg_edit_distance"),
            "avg_rating": health.get("avg_rating"),
        })

    # Project -> Skill links: built from recordings + log files
    links = []
    link_pairs_seen = set()
    recordings_dir = TOOLMASTER_HOME / "recordings"
    if recordings_dir.exists():
        for rf in recordings_dir.glob("*.json"):
            try:
                rec = json.loads(rf.read_text(encoding="utf-8", errors="replace"))
                task = rec.get("task", "")
                # Extract project name from [project]... prefix
                if task.startswith("["):
                    bracket_end = task.find("]")
                    if bracket_end > 0:
                        proj = task[1:bracket_end].replace("delegate", "").strip()
                        # Extract skill names from task (after " — " separator)
                        if " — " in task or " -- " in task:
                            sep = " — " if " — " in task else " -- "
                            skills_part = task.split(sep, 1)[-1].strip()
                            for sk_name in skills_part.split(","):
                                sk_name = sk_name.strip().split("(")[0].strip()
                                if sk_name and len(sk_name) < 50:
                                    pair = (proj, sk_name)
                                    if pair not in link_pairs_seen:
                                        link_pairs_seen.add(pair)
                                        links.append({
                                            "source": f"project:{proj}",
                                            "target": f"skill:{sk_name}",
                                            "type": "uses",
                                        })
            except Exception:
                continue

    # Also scan project data/logs/*.json for deliverables_generated
    import pathlib as _pathlib
    claude_dir = _pathlib.Path(os.environ.get("CLAUDE_DIR", "C:/Claude"))
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
                    for sk_name in log.get("deliverables_generated", []):
                        pair = (proj, sk_name)
                        if pair not in link_pairs_seen:
                            link_pairs_seen.add(pair)
                            links.append({
                                "source": f"project:{proj}",
                                "target": f"skill:{sk_name}",
                                "type": "uses",
                            })
                except Exception:
                    continue

    # Proposals
    proposals_dir = TOOLMASTER_HOME / "proposals"
    proposals = []
    if proposals_dir.exists():
        for pf in sorted(proposals_dir.glob("*.json"))[:50]:
            try:
                p = json.loads(pf.read_text(encoding="utf-8", errors="replace"))
                proposals.append({
                    "id": p.get("id", pf.stem),
                    "type": p.get("type", "unknown"),
                    "title": p.get("title", "")[:80],
                    "source_repo": p.get("source_repo", ""),
                    "safety": p.get("safety", "unknown"),
                    "status": p.get("status", "pending"),
                })
            except Exception:
                continue

    # Scout state summary
    scout_path = TOOLMASTER_HOME / "scout_state.json"
    scout_summary = {"total_cycles": 0, "audited_skills": 0, "known_repos": 0}
    if scout_path.exists():
        try:
            ss = json.loads(scout_path.read_text(encoding="utf-8", errors="replace"))
            scout_summary = {
                "total_cycles": ss.get("total_cycles", 0),
                "audited_skills": len(ss.get("audited_skills", [])),
                "known_repos": len(ss.get("known_repos", [])),
            }
        except Exception:
            pass

    # Loadouts
    loadouts_dir = TOOLMASTER_HOME / "loadouts"
    loadouts = []
    if loadouts_dir.exists():
        for lf in sorted(loadouts_dir.glob("*.json")):
            try:
                lo = json.loads(lf.read_text(encoding="utf-8", errors="replace"))
                loadouts.append({
                    "name": lo["name"],
                    "skills": [s["name"] for s in lo["skills"]],
                })
            except Exception:
                continue

    # Recordings
    recordings_dir = TOOLMASTER_HOME / "recordings"
    recordings_count = 0
    if recordings_dir.exists():
        recordings_count = len(list(recordings_dir.glob("*.json")))

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "skill_nodes": skill_nodes,
        "project_nodes": project_nodes,
        "links": links,
        "proposals": proposals,
        "scout_summary": scout_summary,
        "loadouts": loadouts,
        "recordings_count": recordings_count,
        "total_runs": insights.get("total_runs", 0),
    }


def _render_html(data: dict) -> str:
    """Render the full HTML with inline D3.js, CSS, and data."""

    nodes_json = json.dumps(data["skill_nodes"] + data["project_nodes"])
    links_json = json.dumps(data["links"])
    proposals_json = json.dumps(data["proposals"])
    loadouts_json = json.dumps(data["loadouts"])

    # Summary stats for the header
    total_skills = len(data["skill_nodes"])
    pinned = sum(1 for s in data["skill_nodes"] if s["type"] == "skill")
    tracked = sum(1 for s in data["skill_nodes"] if s["type"] == "tracked")
    projects = len(data["project_nodes"])
    proposals_count = len(data["proposals"])
    safe_proposals = sum(1 for p in data["proposals"] if p["safety"] == "safe")

    # Skill health breakdown
    healthy = sum(1 for s in data["skill_nodes"] if s["avg_edit"] is not None and s["avg_edit"] <= 20)
    moderate = sum(1 for s in data["skill_nodes"] if s["avg_edit"] is not None and 20 < s["avg_edit"] <= 50)
    weak = sum(1 for s in data["skill_nodes"] if s["avg_edit"] is not None and s["avg_edit"] > 50)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ToolMaster Skill Portfolio</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #0d1117; color: #c9d1d9;
    display: flex; height: 100vh; overflow: hidden;
}}
#sidebar {{
    width: 340px; min-width: 340px;
    background: #161b22; border-right: 1px solid #30363d;
    overflow-y: auto; padding: 20px;
}}
#graph {{ flex: 1; position: relative; }}
svg {{ width: 100%; height: 100%; }}

h1 {{ font-size: 18px; color: #f0f6fc; margin-bottom: 4px; }}
.subtitle {{ font-size: 12px; color: #8b949e; margin-bottom: 16px; }}

.stats-grid {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    margin-bottom: 20px;
}}
.stat {{
    background: #21262d; border: 1px solid #30363d; border-radius: 6px;
    padding: 10px; text-align: center;
}}
.stat-value {{ font-size: 22px; font-weight: 700; color: #f0f6fc; }}
.stat-label {{ font-size: 11px; color: #8b949e; margin-top: 2px; }}

.section {{ margin-bottom: 20px; }}
.section-title {{
    font-size: 13px; font-weight: 600; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.5px;
    margin-bottom: 8px; padding-bottom: 4px;
    border-bottom: 1px solid #21262d;
}}

.health-bar {{
    display: flex; height: 8px; border-radius: 4px;
    overflow: hidden; margin-bottom: 12px; background: #21262d;
}}
.health-green {{ background: #3fb950; }}
.health-yellow {{ background: #d29922; }}
.health-red {{ background: #f85149; }}

.skill-row {{
    display: flex; align-items: center; padding: 6px 8px;
    border-radius: 4px; margin-bottom: 2px; font-size: 13px;
    cursor: pointer; transition: background 0.15s;
}}
.skill-row:hover {{ background: #21262d; }}
.skill-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    margin-right: 8px; flex-shrink: 0;
}}
.skill-name {{ flex: 1; color: #c9d1d9; }}
.skill-meta {{ font-size: 11px; color: #8b949e; text-align: right; }}

.proposal-row {{
    padding: 6px 8px; border-radius: 4px; margin-bottom: 2px;
    font-size: 12px; border-left: 3px solid #30363d;
}}
.proposal-row.safe {{ border-left-color: #3fb950; }}
.proposal-row.caution {{ border-left-color: #d29922; }}
.proposal-row.unsafe {{ border-left-color: #f85149; }}
.proposal-title {{ color: #c9d1d9; }}
.proposal-meta {{ color: #8b949e; font-size: 11px; margin-top: 2px; }}

.legend {{
    display: flex; gap: 12px; flex-wrap: wrap;
    margin-bottom: 16px; font-size: 11px;
}}
.legend-item {{ display: flex; align-items: center; gap: 4px; }}
.legend-dot {{
    width: 10px; height: 10px; border-radius: 50%;
}}
.legend-square {{
    width: 10px; height: 10px; border-radius: 2px;
}}

/* Tooltip */
.tooltip {{
    position: absolute; pointer-events: none;
    background: #1c2128; border: 1px solid #30363d;
    border-radius: 6px; padding: 10px 14px;
    font-size: 12px; line-height: 1.5;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    z-index: 100; display: none;
}}
.tooltip-name {{ font-weight: 600; color: #f0f6fc; font-size: 14px; }}
.tooltip-meta {{ color: #8b949e; }}

.footer {{
    font-size: 11px; color: #484f58; text-align: center;
    padding-top: 12px; border-top: 1px solid #21262d;
}}
</style>
</head>
<body>

<div id="sidebar">
    <h1>ToolMaster</h1>
    <div class="subtitle">Skill Portfolio Visualization &mdash; {data["generated_at"]}</div>

    <div class="stats-grid">
        <div class="stat">
            <div class="stat-value">{total_skills}</div>
            <div class="stat-label">Skills ({pinned} pinned, {tracked} tracked)</div>
        </div>
        <div class="stat">
            <div class="stat-value">{projects}</div>
            <div class="stat-label">Projects</div>
        </div>
        <div class="stat">
            <div class="stat-value">{data["scout_summary"]["audited_skills"]}</div>
            <div class="stat-label">External Audited</div>
        </div>
        <div class="stat">
            <div class="stat-value">{proposals_count}</div>
            <div class="stat-label">Proposals ({safe_proposals} safe)</div>
        </div>
        <div class="stat">
            <div class="stat-value">{data["scout_summary"]["known_repos"]}</div>
            <div class="stat-label">Repos Discovered</div>
        </div>
        <div class="stat">
            <div class="stat-value">{data["recordings_count"]}</div>
            <div class="stat-label">Recordings</div>
        </div>
    </div>

    <div class="section">
        <div class="section-title">Skill Health</div>
        <div class="health-bar">
            <div class="health-green" style="width:{_pct(healthy, total_skills)}%"></div>
            <div class="health-yellow" style="width:{_pct(moderate, total_skills)}%"></div>
            <div class="health-red" style="width:{_pct(weak, total_skills)}%"></div>
        </div>
        <div class="legend">
            <span class="legend-item"><span class="legend-dot" style="background:#3fb950"></span> Healthy (&le;20% edit) &mdash; {healthy}</span>
            <span class="legend-item"><span class="legend-dot" style="background:#d29922"></span> Moderate &mdash; {moderate}</span>
            <span class="legend-item"><span class="legend-dot" style="background:#f85149"></span> Weak (&gt;50% edit) &mdash; {weak}</span>
        </div>
    </div>

    <div class="section">
        <div class="section-title">Skills (by usage)</div>
        {"".join(_skill_row_html(s) for s in sorted(data["skill_nodes"], key=lambda x: -(x["runs"] or 0)))}
    </div>

    <div class="section">
        <div class="section-title">Scout Proposals (last {min(len(data["proposals"]), 15)})</div>
        {"".join(_proposal_row_html(p) for p in data["proposals"][:15])}
    </div>

    <div class="section">
        <div class="section-title">Graph Legend</div>
        <div class="legend">
            <span class="legend-item"><span class="legend-dot" style="background:#3fb950"></span> Healthy skill</span>
            <span class="legend-item"><span class="legend-dot" style="background:#d29922"></span> Moderate skill</span>
            <span class="legend-item"><span class="legend-dot" style="background:#f85149"></span> Weak skill</span>
            <span class="legend-item"><span class="legend-dot" style="background:#8b949e"></span> Untracked skill</span>
            <span class="legend-item"><span class="legend-square" style="background:#58a6ff"></span> Project</span>
        </div>
    </div>

    <div class="footer">
        ToolMaster &middot; github.com/techieharry/ToolMaster<br>
        Scout cycles: {data["scout_summary"]["total_cycles"]} &middot;
        Total runs: {data["total_runs"]}
    </div>
</div>

<div id="graph">
    <div class="tooltip" id="tooltip"></div>
    <svg></svg>
</div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const nodes = {nodes_json};
const links = {links_json};
const proposals = {proposals_json};
const loadouts = {loadouts_json};

// Ensure all link endpoints exist
const nodeIds = new Set(nodes.map(n => n.id));
const validLinks = links.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target));

// Color scale
function nodeColor(d) {{
    if (d.type === 'project') return '#58a6ff';
    if (d.avg_edit === null || d.avg_edit === undefined) return '#8b949e';
    if (d.avg_edit <= 20) return '#3fb950';
    if (d.avg_edit <= 50) return '#d29922';
    return '#f85149';
}}

function nodeRadius(d) {{
    if (d.type === 'project') return 18;
    const base = 8;
    const runs = d.runs || 0;
    return Math.min(base + Math.sqrt(runs) * 4, 28);
}}

// SVG setup
const svg = d3.select('svg');
const container = svg.append('g');
const width = window.innerWidth - 340;
const height = window.innerHeight;

// Zoom
svg.call(d3.zoom()
    .scaleExtent([0.2, 4])
    .on('zoom', (e) => container.attr('transform', e.transform))
);

// Force simulation
const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(validLinks).id(d => d.id).distance(80))
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => nodeRadius(d) + 4))
    .force('x', d3.forceX(width / 2).strength(0.05))
    .force('y', d3.forceY(height / 2).strength(0.05));

// Links
const link = container.append('g')
    .selectAll('line')
    .data(validLinks)
    .join('line')
    .attr('stroke', '#30363d')
    .attr('stroke-width', 1.5)
    .attr('stroke-opacity', 0.6);

// Nodes
const node = container.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag()
        .on('start', dragStart)
        .on('drag', dragging)
        .on('end', dragEnd)
    );

// Project nodes = rounded rects, skill nodes = circles
node.each(function(d) {{
    const el = d3.select(this);
    if (d.type === 'project') {{
        el.append('rect')
            .attr('width', 36).attr('height', 24)
            .attr('x', -18).attr('y', -12)
            .attr('rx', 4).attr('ry', 4)
            .attr('fill', nodeColor)
            .attr('stroke', '#30363d').attr('stroke-width', 1.5);
    }} else {{
        el.append('circle')
            .attr('r', nodeRadius)
            .attr('fill', nodeColor)
            .attr('stroke', d.type === 'skill' ? '#30363d' : 'none')
            .attr('stroke-width', 1.5)
            .attr('stroke-dasharray', d.type === 'tracked' ? '3,3' : 'none');
    }}
}});

// Labels
node.append('text')
    .text(d => d.name)
    .attr('font-size', d => d.type === 'project' ? 11 : 10)
    .attr('fill', '#8b949e')
    .attr('text-anchor', 'middle')
    .attr('dy', d => d.type === 'project' ? 24 : nodeRadius(d) + 14);

// Tooltip
const tooltip = d3.select('#tooltip');
node.on('mouseover', (e, d) => {{
    let html = `<div class="tooltip-name">${{d.name}}</div>`;
    if (d.type === 'project') {{
        html += `<div class="tooltip-meta">Project &middot; ${{d.runs || 0}} runs`;
        if (d.avg_edit != null) html += ` &middot; ${{d.avg_edit}}% avg edit`;
        if (d.avg_rating != null) html += ` &middot; ${{d.avg_rating}}/5`;
        html += `</div>`;
    }} else {{
        const status = d.type === 'skill' ? 'Pinned' : 'Tracked (not pinned)';
        html += `<div class="tooltip-meta">${{status}}`;
        if (d.hash) html += ` &middot; ${{d.hash}}`;
        html += `</div>`;
        html += `<div class="tooltip-meta">${{d.runs || 0}} runs`;
        if (d.avg_edit != null) html += ` &middot; ${{d.avg_edit}}% edit`;
        if (d.rejections) html += ` &middot; ${{d.rejections}} rejections`;
        html += `</div>`;
    }}
    tooltip.html(html).style('display', 'block');
}}).on('mousemove', (e) => {{
    tooltip.style('left', (e.pageX + 12) + 'px').style('top', (e.pageY - 20) + 'px');
}}).on('mouseout', () => {{
    tooltip.style('display', 'none');
}});

// Tick
simulation.on('tick', () => {{
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
}});

// Drag
function dragStart(e, d) {{
    if (!e.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x; d.fy = d.y;
}}
function dragging(e, d) {{ d.fx = e.x; d.fy = e.y; }}
function dragEnd(e, d) {{
    if (!e.active) simulation.alphaTarget(0);
    d.fx = null; d.fy = null;
}}
</script>

</body>
</html>"""


def _pct(n: int, total: int) -> int:
    if total == 0:
        return 0
    return max(1, round(n / total * 100))


def _skill_row_html(s: dict) -> str:
    edit = s["avg_edit"]
    if edit is None:
        color = "#8b949e"
    elif edit <= 20:
        color = "#3fb950"
    elif edit <= 50:
        color = "#d29922"
    else:
        color = "#f85149"

    edit_str = f"{edit}%" if edit is not None else "no data"
    rej_str = f" | {s['rejections']} rej" if s["rejections"] else ""
    tag = "pinned" if s["type"] == "skill" else "tracked"

    return (
        f'<div class="skill-row">'
        f'<span class="skill-dot" style="background:{color}"></span>'
        f'<span class="skill-name">{s["name"]}</span>'
        f'<span class="skill-meta">{s["runs"]}x | {edit_str}{rej_str} | {tag}</span>'
        f'</div>\n'
    )


def _proposal_row_html(p: dict) -> str:
    safety_class = p["safety"] if p["safety"] in ("safe", "caution", "unsafe") else ""
    return (
        f'<div class="proposal-row {safety_class}">'
        f'<div class="proposal-title">{p["title"]}</div>'
        f'<div class="proposal-meta">{p["source_repo"]} &middot; {p["type"]} &middot; {p["safety"]}</div>'
        f'</div>\n'
    )
