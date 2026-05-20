#!/usr/bin/env python3
"""
Generate rich HTML analytics dashboard from chats.duckdb.

Usage:
    python3 build_dashboard.py
    python3 build_dashboard.py --db chats.duckdb --output dashboard.html
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb


def query(conn, sql):
    return conn.execute(sql).fetchall()


def collect_data(conn):
    data = {}

    # KPIs
    row = query(conn, """
        SELECT
            COUNT(*) AS total_turns,
            AVG(e.composite_score),
            AVG(e.clarity_score),
            AVG(e.specificity_score),
            AVG(e.intent_score),
            AVG(e.filler_penalty),
            COUNT(DISTINCT c.session_id) AS sessions
        FROM chats c JOIN evaluations e USING (session_id, turn_index)
    """)[0]
    data["kpis"] = {
        "total_turns": row[0],
        "avg_composite": round(row[1], 3),
        "avg_clarity": round(row[2], 3),
        "avg_specificity": round(row[3], 3),
        "avg_intent": round(row[4], 3),
        "avg_filler": round(row[5], 3),
        "sessions": row[6],
    }

    # Monthly volume + avg score
    rows = query(conn, """
        SELECT
            strftime(c.timestamp, '%Y-%m') AS month,
            COUNT(*) AS turns,
            ROUND(AVG(e.composite_score), 3) AS avg_score
        FROM chats c JOIN evaluations e USING (session_id, turn_index)
        WHERE c.timestamp IS NOT NULL
        GROUP BY month
        ORDER BY month
    """)
    data["monthly"] = [{"month": r[0], "turns": r[1], "avg_score": r[2]} for r in rows]

    # Score distributions (clarity / specificity / intent by rating 1-5)
    for dim in ("clarity_score", "specificity_score", "intent_score"):
        rows = query(conn, f"""
            SELECT {dim}, COUNT(*) FROM evaluations
            GROUP BY {dim} ORDER BY {dim}
        """)
        counts = {r[0]: r[1] for r in rows}
        data[f"dist_{dim}"] = [counts.get(i, 0) for i in range(1, 6)]

    # Composite score histogram (buckets of 0.5)
    rows = query(conn, """
        SELECT
            FLOOR(composite_score * 2) / 2 AS bucket,
            COUNT(*) AS cnt
        FROM evaluations
        GROUP BY bucket ORDER BY bucket
    """)
    data["composite_hist"] = [{"bucket": r[0], "count": r[1]} for r in rows]

    # Filler penalty distribution
    rows = query(conn, """
        SELECT filler_penalty, COUNT(*) FROM evaluations
        GROUP BY filler_penalty ORDER BY filler_penalty
    """)
    data["filler_dist"] = [{"penalty": r[0], "count": r[1]} for r in rows]

    # Score by conversation position
    rows = query(conn, """
        SELECT
            CASE
                WHEN turn_index = 0 THEN 'First (0)'
                WHEN turn_index <= 3 THEN 'Early (1-3)'
                WHEN turn_index <= 9 THEN 'Mid (4-9)'
                ELSE 'Late (10+)'
            END AS position,
            ROUND(AVG(composite_score), 3),
            COUNT(*)
        FROM evaluations
        GROUP BY 1
        ORDER BY MIN(turn_index)
    """)
    data["position_scores"] = [{"pos": r[0], "avg": r[1], "count": r[2]} for r in rows]

    # Prompt length buckets vs quality
    rows = query(conn, """
        SELECT
            CASE
                WHEN c.prompt_length_tokens <= 10 THEN '1-10 tokens'
                WHEN c.prompt_length_tokens <= 30 THEN '11-30 tokens'
                WHEN c.prompt_length_tokens <= 100 THEN '31-100 tokens'
                ELSE '100+ tokens'
            END AS bucket,
            ROUND(AVG(e.composite_score), 3),
            COUNT(*)
        FROM chats c JOIN evaluations e USING (session_id, turn_index)
        GROUP BY 1
        ORDER BY MIN(c.prompt_length_tokens)
    """)
    data["length_scores"] = [{"bucket": r[0], "avg": r[1], "count": r[2]} for r in rows]

    # Response length vs composite (buckets)
    rows = query(conn, """
        SELECT
            CASE
                WHEN c.response_length_tokens <= 50 THEN '0-50'
                WHEN c.response_length_tokens <= 200 THEN '51-200'
                WHEN c.response_length_tokens <= 500 THEN '201-500'
                ELSE '500+'
            END AS bucket,
            ROUND(AVG(e.composite_score), 3),
            COUNT(*)
        FROM chats c JOIN evaluations e USING (session_id, turn_index)
        GROUP BY 1
        ORDER BY MIN(c.response_length_tokens)
    """)
    data["response_len_scores"] = [{"bucket": r[0], "avg": r[1], "count": r[2]} for r in rows]

    # Top 10 prompts by composite
    rows = query(conn, """
        SELECT
            c.user_prompt,
            e.composite_score,
            e.clarity_score,
            e.specificity_score,
            e.intent_score,
            e.filler_penalty,
            e.notes,
            c.timestamp
        FROM chats c JOIN evaluations e USING (session_id, turn_index)
        ORDER BY e.composite_score DESC
        LIMIT 10
    """)
    data["top_prompts"] = [
        {
            "prompt": r[0][:300],
            "composite": r[1],
            "clarity": r[2],
            "specificity": r[3],
            "intent": r[4],
            "filler": r[5],
            "notes": r[6],
            "date": str(r[7])[:10] if r[7] else "",
        }
        for r in rows
    ]

    # Bottom 10 prompts
    rows = query(conn, """
        SELECT
            c.user_prompt,
            e.composite_score,
            e.clarity_score,
            e.specificity_score,
            e.intent_score,
            e.filler_penalty,
            e.notes,
            c.timestamp
        FROM chats c JOIN evaluations e USING (session_id, turn_index)
        ORDER BY e.composite_score ASC
        LIMIT 10
    """)
    data["bottom_prompts"] = [
        {
            "prompt": r[0][:300],
            "composite": r[1],
            "clarity": r[2],
            "specificity": r[3],
            "intent": r[4],
            "filler": r[5],
            "notes": r[6],
            "date": str(r[7])[:10] if r[7] else "",
        }
        for r in rows
    ]

    # Best sessions (min 3 turns)
    rows = query(conn, """
        SELECT
            CAST(e.session_id AS VARCHAR),
            ROUND(AVG(e.composite_score), 3),
            COUNT(*) AS turns,
            ROUND(AVG(e.clarity_score), 2),
            ROUND(AVG(e.specificity_score), 2),
            ROUND(AVG(e.intent_score), 2)
        FROM evaluations e
        GROUP BY e.session_id
        HAVING COUNT(*) >= 3
        ORDER BY AVG(e.composite_score) DESC
        LIMIT 15
    """)
    data["best_sessions"] = [
        {
            "session": r[0][:8] + "...",
            "avg_composite": r[1],
            "turns": r[2],
            "clarity": r[3],
            "specificity": r[4],
            "intent": r[5],
        }
        for r in rows
    ]

    # Score correlation buckets (composite vs response length scatter approx)
    rows = query(conn, """
        SELECT
            ROUND(e.composite_score * 2) / 2 AS comp_bucket,
            ROUND(AVG(c.prompt_length_tokens), 1) AS avg_prompt_len,
            ROUND(AVG(c.response_length_tokens), 1) AS avg_resp_len,
            COUNT(*) AS cnt
        FROM chats c JOIN evaluations e USING (session_id, turn_index)
        GROUP BY comp_bucket
        ORDER BY comp_bucket
    """)
    data["score_vs_length"] = [
        {"score": r[0], "avg_prompt": r[1], "avg_response": r[2], "count": r[3]}
        for r in rows
    ]

    return data


def build_html(data: dict, generated_at: str) -> str:
    json_data = json.dumps(data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Prompt Analytics Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #22253a;
    --border: #2e3250;
    --text: #e2e8f0;
    --muted: #8892b0;
    --accent: #6c63ff;
    --accent2: #00d9a3;
    --accent3: #ff6584;
    --accent4: #f6c90e;
    --good: #00d9a3;
    --bad: #ff6584;
    --mid: #f6c90e;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  a {{ color: var(--accent); text-decoration: none; }}

  .header {{ padding: 28px 32px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
  .header h1 {{ font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
  .header .sub {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
  .badge {{ background: var(--accent); color: #fff; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }}

  .main {{ padding: 24px 32px; max-width: 1600px; margin: 0 auto; }}
  .section-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin: 28px 0 14px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }}

  /* KPI Cards */
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; }}
  .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }}
  .kpi-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 28px; font-weight: 800; line-height: 1; }}
  .kpi-sub {{ font-size: 11px; color: var(--muted); margin-top: 4px; }}
  .kpi-good {{ color: var(--good); }}
  .kpi-mid  {{ color: var(--mid); }}
  .kpi-bad  {{ color: var(--bad); }}

  /* Chart Grid */
  .chart-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; }}
  .chart-grid.three {{ grid-template-columns: repeat(3, 1fr); }}
  .chart-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }}
  .chart-card.wide {{ grid-column: span 2; }}
  .chart-title {{ font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 14px; }}
  .chart-wrap {{ position: relative; height: 220px; }}
  .chart-wrap.tall {{ height: 280px; }}

  /* Tables */
  .table-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-bottom: 18px; }}
  .table-card .chart-title {{ padding: 16px 18px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{ background: var(--surface2); color: var(--muted); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.6px; padding: 10px 14px; text-align: left; }}
  tbody tr {{ border-top: 1px solid var(--border); }}
  tbody tr:hover {{ background: var(--surface2); }}
  tbody td {{ padding: 10px 14px; vertical-align: top; }}
  .prompt-text {{ max-width: 480px; color: var(--text); line-height: 1.5; }}
  .score-pill {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 12px; }}
  .pill-good {{ background: #00d9a31a; color: var(--good); }}
  .pill-mid  {{ background: #f6c90e1a; color: var(--mid); }}
  .pill-bad  {{ background: #ff65841a; color: var(--bad); }}
  .notes-cell {{ color: var(--muted); font-style: italic; max-width: 240px; }}
  .date-cell {{ color: var(--muted); white-space: nowrap; }}

  @media (max-width: 900px) {{
    .chart-grid {{ grid-template-columns: 1fr; }}
    .chart-card.wide {{ grid-column: span 1; }}
    .main {{ padding: 16px; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Prompt Analytics Dashboard</h1>
    <div class="sub">Generated {generated_at} &mdash; Claude conversation data</div>
  </div>
  <span class="badge">Claude</span>
</div>

<div class="main">

<div class="section-title">Overview</div>
<div class="kpi-grid" id="kpi-grid"></div>

<div class="section-title">Activity Over Time</div>
<div class="chart-grid">
  <div class="chart-card">
    <div class="chart-title">Monthly Turn Volume</div>
    <div class="chart-wrap"><canvas id="monthlyVolume"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Avg Composite Score by Month</div>
    <div class="chart-wrap"><canvas id="monthlyScore"></canvas></div>
  </div>
</div>

<div class="section-title">Score Distributions</div>
<div class="chart-grid">
  <div class="chart-card wide">
    <div class="chart-title">Score Dimensions — Rating Distribution (1–5)</div>
    <div class="chart-wrap"><canvas id="scoreDistGrouped"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Composite Score Histogram</div>
    <div class="chart-wrap"><canvas id="compositeHist"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Filler Penalty Distribution</div>
    <div class="chart-wrap"><canvas id="fillerDist"></canvas></div>
  </div>
</div>

<div class="section-title">Quality Patterns</div>
<div class="chart-grid three">
  <div class="chart-card">
    <div class="chart-title">Score by Position in Conversation</div>
    <div class="chart-wrap"><canvas id="positionScore"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Score by Prompt Length</div>
    <div class="chart-wrap"><canvas id="lengthScore"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Score by Response Length Received</div>
    <div class="chart-wrap"><canvas id="respLenScore"></canvas></div>
  </div>
</div>

<div class="section-title">Score vs Prompt Length Relationship</div>
<div class="chart-grid">
  <div class="chart-card">
    <div class="chart-title">Avg Prompt Length by Composite Score</div>
    <div class="chart-wrap"><canvas id="svlPrompt"></canvas></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">Avg Response Length by Composite Score</div>
    <div class="chart-wrap"><canvas id="svlResponse"></canvas></div>
  </div>
</div>

<div class="section-title">Best Sessions (min 3 turns)</div>
<div class="table-card">
  <table id="best-sessions-table">
    <thead><tr>
      <th>Session</th>
      <th>Composite</th>
      <th>Clarity</th>
      <th>Specificity</th>
      <th>Intent</th>
      <th>Turns</th>
    </tr></thead>
    <tbody id="best-sessions-body"></tbody>
  </table>
</div>

<div class="section-title">Top 10 Prompts by Quality</div>
<div class="table-card">
  <table>
    <thead><tr>
      <th>Prompt</th>
      <th>Score</th>
      <th>C/S/I</th>
      <th>Notes</th>
      <th>Date</th>
    </tr></thead>
    <tbody id="top-prompts-body"></tbody>
  </table>
</div>

<div class="section-title">Bottom 10 Prompts by Quality</div>
<div class="table-card">
  <table>
    <thead><tr>
      <th>Prompt</th>
      <th>Score</th>
      <th>C/S/I</th>
      <th>Notes</th>
      <th>Date</th>
    </tr></thead>
    <tbody id="bottom-prompts-body"></tbody>
  </table>
</div>

</div><!-- .main -->

<script>
const D = {json_data};

// ── Helpers ──────────────────────────────────────────────────────────────────
function scoreColor(v) {{
  if (v >= 4) return 'pill-good';
  if (v >= 2.5) return 'pill-mid';
  return 'pill-bad';
}}
function pill(v) {{
  return `<span class="score-pill ${{scoreColor(v)}}">${{typeof v === 'number' ? v.toFixed(2) : v}}</span>`;
}}
const ACCENT   = '#6c63ff';
const ACCENT2  = '#00d9a3';
const ACCENT3  = '#ff6584';
const ACCENT4  = '#f6c90e';
const MUTED    = '#8892b0';
const SURFACE2 = '#22253a';

const baseOpts = {{
  responsive: true,
  maintainAspectRatio: false,
  plugins: {{ legend: {{ labels: {{ color: '#8892b0', boxWidth: 12, font: {{ size: 11 }} }} }} }},
  scales: {{
    x: {{ ticks: {{ color: MUTED, font: {{ size: 11 }} }}, grid: {{ color: '#1e2235' }} }},
    y: {{ ticks: {{ color: MUTED, font: {{ size: 11 }} }}, grid: {{ color: '#1e2235' }} }},
  }}
}};
function merge(a, b) {{ return Object.assign({{...a}}, b, {{ plugins: Object.assign({{...a.plugins}}, b.plugins||{{}}), scales: Object.assign({{...a.scales}}, b.scales||{{}}) }}); }}

// ── KPI Cards ────────────────────────────────────────────────────────────────
const kpis = [
  {{ label: 'Total Turns',    value: D.kpis.total_turns,    sub: `${{D.kpis.sessions}} sessions`,   cls: '' }},
  {{ label: 'Composite Score', value: D.kpis.avg_composite.toFixed(2), sub: 'avg across all turns', cls: scoreColor(D.kpis.avg_composite).replace('pill-','kpi-') }},
  {{ label: 'Clarity',        value: D.kpis.avg_clarity.toFixed(2),    sub: 'avg score 1-5', cls: scoreColor(D.kpis.avg_clarity).replace('pill-','kpi-') }},
  {{ label: 'Specificity',    value: D.kpis.avg_specificity.toFixed(2),sub: 'avg score 1-5', cls: scoreColor(D.kpis.avg_specificity).replace('pill-','kpi-') }},
  {{ label: 'Intent',         value: D.kpis.avg_intent.toFixed(2),     sub: 'avg score 1-5', cls: scoreColor(D.kpis.avg_intent).replace('pill-','kpi-') }},
  {{ label: 'Filler Penalty', value: D.kpis.avg_filler.toFixed(2),     sub: 'avg 0-3', cls: D.kpis.avg_filler > 1 ? 'kpi-bad' : D.kpis.avg_filler > 0.4 ? 'kpi-mid' : 'kpi-good' }},
];
const kpiGrid = document.getElementById('kpi-grid');
kpis.forEach(k => {{
  kpiGrid.innerHTML += `
    <div class="kpi-card">
      <div class="kpi-label">${{k.label}}</div>
      <div class="kpi-value ${{k.cls}}">${{k.value}}</div>
      <div class="kpi-sub">${{k.sub}}</div>
    </div>`;
}});

// ── Monthly Volume ────────────────────────────────────────────────────────────
new Chart(document.getElementById('monthlyVolume'), {{
  type: 'bar',
  data: {{
    labels: D.monthly.map(r => r.month),
    datasets: [{{ label: 'Turns', data: D.monthly.map(r => r.turns), backgroundColor: ACCENT + 'cc', borderRadius: 4 }}]
  }},
  options: merge(baseOpts, {{ plugins: {{ legend: {{ display: false }} }} }})
}});

// ── Monthly Score ─────────────────────────────────────────────────────────────
new Chart(document.getElementById('monthlyScore'), {{
  type: 'line',
  data: {{
    labels: D.monthly.map(r => r.month),
    datasets: [{{ label: 'Avg Composite', data: D.monthly.map(r => r.avg_score),
      borderColor: ACCENT2, backgroundColor: ACCENT2 + '22',
      tension: 0.3, fill: true, pointRadius: 4, pointBackgroundColor: ACCENT2 }}]
  }},
  options: merge(baseOpts, {{ scales: {{ y: {{ min: 0, max: 5 }} }} }})
}});

// ── Score Dist Grouped ────────────────────────────────────────────────────────
new Chart(document.getElementById('scoreDistGrouped'), {{
  type: 'bar',
  data: {{
    labels: ['1', '2', '3', '4', '5'],
    datasets: [
      {{ label: 'Clarity',     data: D.dist_clarity_score,     backgroundColor: ACCENT  + 'cc', borderRadius: 3 }},
      {{ label: 'Specificity', data: D.dist_specificity_score, backgroundColor: ACCENT2 + 'cc', borderRadius: 3 }},
      {{ label: 'Intent',      data: D.dist_intent_score,      backgroundColor: ACCENT4 + 'cc', borderRadius: 3 }},
    ]
  }},
  options: merge(baseOpts, {{ scales: {{ x: {{ title: {{ display: true, text: 'Rating', color: MUTED }} }} }} }})
}});

// ── Composite Histogram ───────────────────────────────────────────────────────
new Chart(document.getElementById('compositeHist'), {{
  type: 'bar',
  data: {{
    labels: D.composite_hist.map(r => r.bucket.toFixed(1)),
    datasets: [{{ label: 'Turns', data: D.composite_hist.map(r => r.count),
      backgroundColor: ACCENT3 + 'bb', borderRadius: 3 }}]
  }},
  options: merge(baseOpts, {{ plugins: {{ legend: {{ display: false }} }} }})
}});

// ── Filler Dist ───────────────────────────────────────────────────────────────
new Chart(document.getElementById('fillerDist'), {{
  type: 'bar',
  data: {{
    labels: D.filler_dist.map(r => 'Penalty ' + r.penalty),
    datasets: [{{ label: 'Turns', data: D.filler_dist.map(r => r.count),
      backgroundColor: [ACCENT2+'cc', ACCENT4+'cc', ACCENT3+'cc', '#ff2222cc'].slice(0, D.filler_dist.length),
      borderRadius: 4 }}]
  }},
  options: merge(baseOpts, {{ plugins: {{ legend: {{ display: false }} }} }})
}});

// ── Position Score ────────────────────────────────────────────────────────────
new Chart(document.getElementById('positionScore'), {{
  type: 'bar',
  data: {{
    labels: D.position_scores.map(r => r.pos),
    datasets: [{{ label: 'Avg Composite', data: D.position_scores.map(r => r.avg),
      backgroundColor: ACCENT + 'cc', borderRadius: 4 }}]
  }},
  options: merge(baseOpts, {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ min: 0, max: 5 }} }} }})
}});

// ── Length Score ──────────────────────────────────────────────────────────────
new Chart(document.getElementById('lengthScore'), {{
  type: 'bar',
  data: {{
    labels: D.length_scores.map(r => r.bucket),
    datasets: [{{ label: 'Avg Composite', data: D.length_scores.map(r => r.avg),
      backgroundColor: ACCENT2 + 'cc', borderRadius: 4 }}]
  }},
  options: merge(baseOpts, {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ min: 0, max: 5 }} }} }})
}});

// ── Response Length Score ─────────────────────────────────────────────────────
new Chart(document.getElementById('respLenScore'), {{
  type: 'bar',
  data: {{
    labels: D.response_len_scores.map(r => r.bucket),
    datasets: [{{ label: 'Avg Composite', data: D.response_len_scores.map(r => r.avg),
      backgroundColor: ACCENT4 + 'cc', borderRadius: 4 }}]
  }},
  options: merge(baseOpts, {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ min: 0, max: 5 }} }} }})
}});

// ── Score vs Length ───────────────────────────────────────────────────────────
new Chart(document.getElementById('svlPrompt'), {{
  type: 'bar',
  data: {{
    labels: D.score_vs_length.map(r => r.score.toFixed(1)),
    datasets: [{{ label: 'Avg Prompt Tokens', data: D.score_vs_length.map(r => r.avg_prompt),
      backgroundColor: ACCENT + 'aa', borderRadius: 3 }}]
  }},
  options: merge(baseOpts, {{ scales: {{ x: {{ title: {{ display: true, text: 'Composite Score', color: MUTED }} }} }} }})
}});

new Chart(document.getElementById('svlResponse'), {{
  type: 'bar',
  data: {{
    labels: D.score_vs_length.map(r => r.score.toFixed(1)),
    datasets: [{{ label: 'Avg Response Tokens', data: D.score_vs_length.map(r => r.avg_response),
      backgroundColor: ACCENT2 + 'aa', borderRadius: 3 }}]
  }},
  options: merge(baseOpts, {{ scales: {{ x: {{ title: {{ display: true, text: 'Composite Score', color: MUTED }} }} }} }})
}});

// ── Best Sessions Table ───────────────────────────────────────────────────────
const sessBody = document.getElementById('best-sessions-body');
D.best_sessions.forEach(r => {{
  sessBody.innerHTML += `<tr>
    <td><code style="color:#8892b0;font-size:11px">${{r.session}}</code></td>
    <td>${{pill(r.avg_composite)}}</td>
    <td><span style="color:#8892b0">${{r.clarity}}</span></td>
    <td><span style="color:#8892b0">${{r.specificity}}</span></td>
    <td><span style="color:#8892b0">${{r.intent}}</span></td>
    <td><span style="color:#8892b0">${{r.turns}}</span></td>
  </tr>`;
}});

// ── Prompt Tables ─────────────────────────────────────────────────────────────
function promptRow(r) {{
  return `<tr>
    <td class="prompt-text">${{r.prompt.replace(/</g,'&lt;').replace(/>/g,'&gt;')}}</td>
    <td>${{pill(r.composite)}}</td>
    <td style="white-space:nowrap;color:#8892b0;font-size:12px">${{r.clarity}}/${{r.specificity}}/${{r.intent}}</td>
    <td class="notes-cell">${{r.notes}}</td>
    <td class="date-cell">${{r.date}}</td>
  </tr>`;
}}
document.getElementById('top-prompts-body').innerHTML = D.top_prompts.map(promptRow).join('');
document.getElementById('bottom-prompts-body').innerHTML = D.bottom_prompts.map(promptRow).join('');
</script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build analytics dashboard from chats.duckdb")
    parser.add_argument("--db", default="chats.duckdb")
    parser.add_argument("--output", default="analytics_dashboard.html")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: {args.db} not found. Run load_duckdb.py first.")
        sys.exit(1)

    conn = duckdb.connect(args.db, read_only=True)
    data = collect_data(conn)
    conn.close()

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = build_html(data, generated_at)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
