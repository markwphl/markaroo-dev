#!/usr/bin/env python3
"""
Flask web interface for the Government ArcGIS Feature Layer Scanner.

Run with:
    python web_app.py
    # or
    flask --app web_app run --host 0.0.0.0 --port 5000

Provides:
    - Form to enter a government website URL
    - Real-time progress via Server-Sent Events (SSE)
    - Summary statistics table
    - Download buttons for Excel and Markdown output files
"""

import json
import os
import queue
import threading
import uuid
from html import escape

from flask import Flask, Response, jsonify, render_template_string, request, send_file

from gov_arcgis_scanner import scan

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# In-flight scan jobs: job_id -> {queue, result, status}
_jobs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# HTML template (single-page app, no external dependencies)
# ---------------------------------------------------------------------------

INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GIS Data Finder</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  :root {
    --bg: #ece7df;
    --surface: #ffffff;
    --surface-alt: #f5f1ec;
    --border: #d6d0c8;
    --border-light: #e4dfd8;
    --text: #2c2c2c;
    --text-secondary: #6b6560;
    --text-muted: #8c857e;
    --accent: #1a5c50;
    --accent-hover: #154a41;
    --accent-light: #e8f0ee;
    --green: #2d7a4f;
    --green-bg: #e6f4ec;
    --red: #c0392b;
    --red-bg: #fdecea;
    --amber: #8b6914;
    --amber-bg: #fef9ec;
    --sidebar-w: 260px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
  }

  /* ---- Sidebar ---- */
  .sidebar {
    width: var(--sidebar-w);
    min-height: 100vh;
    background: var(--surface);
    border-right: 1px solid var(--border-light);
    padding: 1.5rem 0;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
  }
  .sidebar-brand {
    padding: 0 1.25rem 1.25rem;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: .75rem;
  }
  .sidebar-brand h2 {
    font-size: .95rem;
    font-weight: 700;
    color: var(--text);
    letter-spacing: -.01em;
  }
  .sidebar-brand p {
    font-size: .75rem;
    color: var(--text-muted);
    margin-top: .15rem;
  }
  .sidebar-section {
    padding: .6rem 1.25rem .2rem;
    font-size: .7rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .06em;
  }
  .sidebar-item {
    display: flex;
    align-items: center;
    gap: .6rem;
    padding: .5rem 1.25rem;
    font-size: .85rem;
    color: var(--text-secondary);
    text-decoration: none;
    cursor: pointer;
    transition: background .12s, color .12s;
    border: none;
    background: none;
    width: 100%;
    text-align: left;
    font-family: inherit;
  }
  .sidebar-item:hover { background: var(--surface-alt); color: var(--text); }
  .sidebar-item.active { color: var(--accent); font-weight: 500; }
  .sidebar-item svg { width: 18px; height: 18px; flex-shrink: 0; opacity: .7; }
  .sidebar-item.active svg { opacity: 1; }
  .sidebar-item .check { margin-left: auto; color: var(--accent); font-size: .85rem; }
  .sidebar-spacer { flex: 1; }
  .sidebar-footer {
    padding: .75rem 1.25rem;
    border-top: 1px solid var(--border-light);
    font-size: .72rem;
    color: var(--text-muted);
  }

  /* ---- Main content ---- */
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 3rem 2rem 2rem;
    overflow-y: auto;
    min-height: 100vh;
  }

  .hero-title {
    font-size: 1.75rem;
    font-weight: 300;
    color: var(--accent);
    margin-bottom: 2rem;
    text-align: center;
  }

  /* ---- Input card ---- */
  .input-card {
    width: 100%;
    max-width: 680px;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: 1rem;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
    margin-bottom: .5rem;
  }
  .context-bar {
    font-size: .78rem;
    color: var(--text-muted);
    margin-bottom: .6rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .context-bar a { color: var(--accent); text-decoration: none; font-weight: 500; }
  .input-row {
    display: flex;
    align-items: center;
    gap: .75rem;
  }
  .input-row input[type="url"] {
    flex: 1;
    border: none;
    outline: none;
    background: #f0f0f0;
    font-family: inherit;
    font-size: .95rem;
    color: var(--text);
    padding: .5rem .75rem;
    border-radius: .5rem;
  }
  .input-row input[type="url"]::placeholder { color: var(--text-muted); }
  .btn-submit {
    width: 38px; height: 38px;
    border-radius: 50%;
    border: none;
    background: var(--accent);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: background .15s;
  }
  .btn-submit:hover { background: var(--accent-hover); }
  .btn-submit:disabled { opacity: .35; cursor: not-allowed; }
  .btn-submit svg { width: 18px; height: 18px; }

  .hint {
    text-align: center;
    font-size: .72rem;
    color: var(--text-muted);
    margin-top: .5rem;
    margin-bottom: 2rem;
  }

  /* ---- Radio group ---- */
  .radio-group {
    display: flex;
    flex-direction: column;
    gap: .45rem;
    margin-bottom: .75rem;
  }
  .radio-group label {
    display: flex;
    align-items: flex-start;
    gap: .5rem;
    font-size: .82rem;
    color: var(--text-secondary);
    cursor: pointer;
    padding: .35rem .5rem;
    border-radius: .5rem;
    transition: background .12s;
  }
  .radio-group label:hover { background: var(--surface-alt); }
  .radio-group label.selected { background: var(--accent-light); color: var(--text); }
  .radio-group input[type="radio"] {
    accent-color: var(--accent);
    margin-top: .15rem;
    flex-shrink: 0;
  }
  .radio-label-text strong {
    display: block;
    font-size: .82rem;
    font-weight: 600;
    color: var(--text);
    line-height: 1.3;
  }
  .radio-label-text span {
    font-size: .72rem;
    color: var(--text-muted);
    line-height: 1.3;
  }

  /* ---- Status line ---- */
  #status-line {
    text-align: center;
    font-size: .85rem;
    color: var(--text-secondary);
    margin-bottom: 1rem;
    min-height: 1.2em;
  }
  .spinner {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2.5px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin .65s linear infinite;
    vertical-align: middle;
    margin-right: .35rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ---- Tabs ---- */
  .tabs {
    display: none;
    width: 100%;
    max-width: 680px;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 1rem;
    gap: 0;
  }
  .tabs.visible { display: flex; }
  .tab-btn {
    padding: .6rem 1.25rem;
    font-family: inherit;
    font-size: .85rem;
    font-weight: 500;
    color: var(--text-muted);
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: color .15s, border-color .15s;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active { color: var(--text); border-bottom-color: var(--accent); }

  /* ---- Progress log ---- */
  #progress-box {
    display: none;
    width: 100%;
    max-width: 680px;
    max-height: 280px;
    overflow-y: auto;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: .75rem;
    padding: 1rem 1.25rem;
    font-size: .8rem;
    line-height: 1.65;
    margin-bottom: 1rem;
  }
  #progress-box .log { color: var(--text-secondary); }
  #progress-box .stat { color: var(--amber); font-weight: 500; }
  #progress-box .error { color: var(--red); }
  #progress-box .done { color: var(--green); font-weight: 600; }

  /* ---- Summary ---- */
  #summary {
    display: none;
    width: 100%;
    max-width: 680px;
    margin-bottom: 1rem;
  }
  #summary h3 {
    font-size: .8rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .05em;
    margin-bottom: .5rem;
  }
  #summary table { width: 100%; border-collapse: collapse; }
  #summary th, #summary td {
    text-align: left;
    padding: .45rem .75rem;
    font-size: .85rem;
  }
  #summary tr { border-bottom: 1px solid var(--border-light); }
  #summary th { color: var(--text-secondary); font-weight: 500; }
  #summary td { color: var(--text); font-weight: 600; }

  /* ---- Downloads ---- */
  #downloads {
    display: none;
    width: 100%;
    max-width: 680px;
    margin-bottom: 1.25rem;
  }
  .btn-download {
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    padding: .55rem 1.1rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: .6rem;
    font-family: inherit;
    font-size: .85rem;
    font-weight: 500;
    color: var(--text);
    text-decoration: none;
    margin-right: .5rem;
    margin-bottom: .5rem;
    transition: background .12s, border-color .12s;
    cursor: pointer;
  }
  .btn-download:hover { background: var(--surface-alt); border-color: var(--accent); }
  .btn-download svg { width: 16px; height: 16px; color: var(--accent); }

  /* ---- Results table ---- */
  #results-table {
    display: none;
    width: 100%;
    max-width: 680px;
    margin-bottom: 1rem;
  }
  #results-table h3 {
    font-size: .8rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .05em;
    margin-bottom: .5rem;
  }
  .table-scroll {
    max-height: 340px;
    overflow: auto;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: .75rem;
  }
  #results-table table { width: 100%; border-collapse: collapse; font-size: .8rem; }
  #results-table th {
    background: var(--surface-alt);
    color: var(--text-secondary);
    font-weight: 600;
    position: sticky;
    top: 0;
    z-index: 1;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .04em;
  }
  #results-table th, #results-table td {
    padding: .5rem .75rem;
    border-bottom: 1px solid var(--border-light);
    text-align: left;
    white-space: nowrap;
    max-width: 240px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #results-table tr:last-child td { border-bottom: none; }
  #results-table tr:hover td { background: var(--surface-alt); }
  #results-table td:nth-child(4) { font-family: 'SF Mono', 'Cascadia Code', monospace; font-size: .72rem; color: var(--text-secondary); }

  /* ---- Quick-action cards (bottom) ---- */
  .quick-actions {
    display: none;
    width: 100%;
    max-width: 680px;
    gap: .6rem;
    flex-wrap: wrap;
  }
  .quick-actions.visible { display: flex; }
  .action-card {
    flex: 1 1 calc(50% - .3rem);
    min-width: 200px;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: .6rem;
    padding: .65rem 1rem;
    font-family: inherit;
    font-size: .85rem;
    color: var(--text-secondary);
    cursor: pointer;
    transition: background .12s, border-color .12s;
    text-align: left;
    border-bottom: none;
    display: block;
    text-decoration: none;
  }
  .action-card:hover { background: var(--surface-alt); border-color: var(--accent); color: var(--text); }

  /* ---- Responsive ---- */
  @media (max-width: 800px) {
    .sidebar { display: none; }
    .main { padding: 2rem 1rem; }
    .hero-title { font-size: 1.35rem; }
  }
</style>
</head>
<body>

<!-- ====== Sidebar ====== -->
<aside class="sidebar">
  <div class="sidebar-brand">
    <h2>GIS Data Finder</h2>
    <p>Search for a client's GIS Layers and endpoints</p>
  </div>

  <div class="sidebar-section">Scanner</div>
  <button class="sidebar-item active" onclick="showPanel('scan')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    New Scan
    <span class="check">&#10003;</span>
  </button>

  <div class="sidebar-spacer"></div>
  <div class="sidebar-footer">v1.0 &middot; Intranet Tool</div>
</aside>

<!-- ====== Main content ====== -->
<main class="main">
  <h1 class="hero-title">How can I help you prepare a GIS Layer List for the Planning Data Table?</h1>

  <!-- Input -->
  <div class="input-card">
    <div class="context-bar">
      <span>Pick a search option and insert the applicable URL below.</span>
      <a href="#" onclick="return false;">Details</a>
    </div>

    <div class="radio-group" id="mode-group">
      <label class="selected" for="mode-direct">
        <input type="radio" id="mode-direct" name="scan-mode" value="direct" checked>
        <div class="radio-label-text">
          <strong>ArcGIS REST Services Directory</strong>
          <span>I have the root URL to the jurisdiction's ArcGIS REST services directory</span>
        </div>
      </label>
      <label for="mode-homepage">
        <input type="radio" id="mode-homepage" name="scan-mode" value="homepage">
        <div class="radio-label-text">
          <strong>Jurisdiction's Main Website</strong>
          <span>I have the jurisdiction's homepage &mdash; scan will crawl for GIS endpoints</span>
        </div>
      </label>
      <label for="mode-gispage">
        <input type="radio" id="mode-gispage" name="scan-mode" value="gis_page">
        <div class="radio-label-text">
          <strong>GIS Resources / Department Page</strong>
          <span>I have the URL to the jurisdiction's GIS, open data, or department page</span>
        </div>
      </label>
    </div>

    <form id="scan-form" class="input-row">
      <input id="url-input" type="url" name="url" required
             placeholder="Insert web address here"
             autocomplete="url">
      <button type="submit" class="btn-submit" id="scan-btn" title="Start scan">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
      </button>
    </form>
  </div>
  <p class="hint" id="hint-text">The tool finds GIS layers from the client's published directory of ArcGIS REST services (API endpoints). Only GIS layers found to be applicable to the Planning knowledge domain are enumerated (with effort to remove duplicates) and output to a table. Double check this list with your client for the correct feature layers and endpoint URLs.</p>

  <!-- Status -->
  <div id="status-line"></div>

  <!-- Tabs -->
  <div class="tabs" id="tabs">
    <button class="tab-btn active" data-tab="progress" onclick="switchTab(this)">Progress</button>
    <button class="tab-btn" data-tab="results" onclick="switchTab(this)">Results</button>
    <button class="tab-btn" data-tab="summary" onclick="switchTab(this)">Summary</button>
  </div>

  <!-- Tab panels -->
  <div id="progress-box"></div>

  <div id="results-table"></div>

  <div id="summary">
    <h3>Scan Statistics</h3>
    <table><tbody id="summary-body"></tbody></table>
  </div>

  <div id="downloads"></div>

</main>

<script>
const form = document.getElementById('scan-form');
const btn = document.getElementById('scan-btn');
const box = document.getElementById('progress-box');
const statusLine = document.getElementById('status-line');
const summaryDiv = document.getElementById('summary');
const summaryBody = document.getElementById('summary-body');
const downloadsDiv = document.getElementById('downloads');
const resultsDiv = document.getElementById('results-table');
const tabs = document.getElementById('tabs');

const hintEl = document.getElementById('hint-text');
const modeGroup = document.getElementById('mode-group');

const MODE_CONFIG = {
  direct: {
    placeholder: 'Insert web address here',
    hint: 'The tool finds GIS layers from the client's published directory of ArcGIS REST services (API endpoints). Only GIS layers found to be applicable to the Planning knowledge domain are enumerated (with effort to remove duplicates) and output to a table. Double check this list with your client for the correct feature layers and endpoint URLs.'
  },
  homepage: {
    placeholder: 'Insert web address here',
    hint: 'Crawls the jurisdiction website to discover ArcGIS REST endpoints.'
  },
  gis_page: {
    placeholder: 'Insert web address here',
    hint: 'Scans the GIS department page for ArcGIS REST endpoint links.'
  }
};

function getSelectedMode() {
  return document.querySelector('input[name="scan-mode"]:checked').value;
}

// Update placeholder and hint when radio selection changes
modeGroup.addEventListener('change', (e) => {
  if (e.target.name !== 'scan-mode') return;
  const mode = e.target.value;
  const cfg = MODE_CONFIG[mode];
  document.getElementById('url-input').placeholder = cfg.placeholder;
  hintEl.textContent = cfg.hint;
  // Highlight selected label
  modeGroup.querySelectorAll('label').forEach(l => l.classList.remove('selected'));
  e.target.closest('label').classList.add('selected');
});

function prefill(url) {
  document.getElementById('url-input').value = url;
  document.getElementById('url-input').focus();
}

function showPanel(name) { /* placeholder for sidebar navigation */ }

function switchTab(el) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  const t = el.dataset.tab;
  box.style.display = t === 'progress' ? 'block' : 'none';
  resultsDiv.style.display = t === 'results' ? 'block' : 'none';
  summaryDiv.style.display = t === 'summary' ? 'block' : 'none';
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = document.getElementById('url-input').value.trim();
  if (!url) return;

  // Reset UI
  box.innerHTML = ''; box.style.display = 'block';
  summaryDiv.style.display = 'none'; summaryBody.innerHTML = '';
  downloadsDiv.style.display = 'none'; downloadsDiv.innerHTML = '';
  resultsDiv.style.display = 'none'; resultsDiv.innerHTML = '';
  tabs.classList.add('visible');
  // Activate progress tab
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.tab-btn[data-tab="progress"]').classList.add('active');
  btn.disabled = true;
  statusLine.innerHTML = '<span class="spinner"></span> Scanning&hellip;';

  // Start scan
  const mode = getSelectedMode();
  let res;
  try {
    res = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, mode})
    });
  } catch (err) {
    statusLine.textContent = 'Network error \u2013 could not reach server.';
    btn.disabled = false;
    return;
  }
  const {job_id, error} = await res.json();
  if (error) {
    addLine('error', error);
    statusLine.textContent = 'Failed.';
    btn.disabled = false;
    return;
  }

  // SSE progress stream
  const evtSource = new EventSource(`/api/progress/${job_id}`);

  evtSource.addEventListener('log', (e) => { addLine('log', e.data); });
  evtSource.addEventListener('stat', (e) => { addLine('stat', e.data); });
  evtSource.addEventListener('error_msg', (e) => { addLine('error', e.data); });

  evtSource.addEventListener('summary', (e) => {
    const stats = JSON.parse(e.data);
    summaryBody.innerHTML = '';
    for (const [k, v] of Object.entries(stats)) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<th>${esc(k)}</th><td>${esc(String(v))}</td>`;
      summaryBody.appendChild(tr);
    }
  });

  evtSource.addEventListener('done', (e) => {
    evtSource.close();
    const data = JSON.parse(e.data);
    statusLine.innerHTML = '<span style="color:var(--green);">&#10003;</span> Scan complete';
    btn.disabled = false;

    if (data.error) {
      addLine('error', data.error);
      return;
    }

    // Download links
    downloadsDiv.innerHTML = '';
    if (data.xl_file) {
      downloadsDiv.innerHTML += `<a class="btn-download" href="/api/download/${job_id}/xlsx"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Excel (.xlsx)</a>`;
    }
    if (data.md_file) {
      downloadsDiv.innerHTML += `<a class="btn-download" href="/api/download/${job_id}/md"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Markdown (.md)</a>`;
    }
    downloadsDiv.style.display = 'block';

    // Build preview table
    if (data.layers && data.layers.length) {
      let html = '<h3>Results Preview</h3>';
      html += '<div class="table-scroll">';
      html += '<table><thead><tr><th>GIS Layer Name</th><th>Source System</th><th>Collection</th><th>API Endpoint</th><th>Time Period</th><th>Update Freq.</th></tr></thead><tbody>';
      data.layers.forEach(l => {
        html += `<tr><td>${esc(l.layer_name)}</td><td>Esri ArcGIS</td><td>API</td><td title="${esc(l.layer_url)}">${esc(l.layer_url)}</td><td>Current</td><td>Ad Hoc</td></tr>`;
      });
      html += '</tbody></table></div>';
      resultsDiv.innerHTML = html;
    }

    // Auto-switch to results tab
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.tab-btn[data-tab="results"]').classList.add('active');
    box.style.display = 'none';
    resultsDiv.style.display = 'block';
    summaryDiv.style.display = 'none';
  });

  evtSource.onerror = () => {
    evtSource.close();
    statusLine.textContent = 'Connection lost.';
    btn.disabled = false;
  };
});

function addLine(cls, text) {
  const div = document.createElement('div');
  div.className = cls;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    mode = (data.get("mode") or "homepage").strip()
    if not url:
        return jsonify({"error": "URL is required."}), 400
    if mode not in ("direct", "homepage", "gis_page"):
        return jsonify({"error": "Invalid mode."}), 400

    job_id = uuid.uuid4().hex[:12]
    q: queue.Queue = queue.Queue()
    _jobs[job_id] = {"queue": q, "result": None, "status": "running"}

    def progress_cb(event_type: str, message: str):
        q.put((event_type, message))

    def run():
        try:
            job_output_dir = os.path.join(OUTPUT_DIR, job_id)
            result = scan(url, output_dir=job_output_dir, progress_callback=progress_cb,
                          mode=mode)
            _jobs[job_id]["result"] = result
            _jobs[job_id]["status"] = "done"
            q.put(("done", json.dumps({
                "xl_file": result.get("xl_path"),
                "md_file": result.get("md_path"),
                "layers": result.get("layers", []),
                "error": result.get("error"),
            })))
        except Exception as exc:
            _jobs[job_id]["status"] = "error"
            q.put(("error_msg", str(exc)))
            q.put(("done", json.dumps({"error": str(exc)})))

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    job = _jobs.get(job_id)
    if not job:
        return "Job not found", 404

    def stream():
        q = job["queue"]
        while True:
            try:
                event_type, message = q.get(timeout=120)
            except queue.Empty:
                # Keep-alive
                yield ": keepalive\n\n"
                continue
            yield f"event: {event_type}\ndata: {message}\n\n"
            if event_type == "done":
                break

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/download/<job_id>/<fmt>")
def api_download(job_id, fmt):
    job = _jobs.get(job_id)
    if not job or not job.get("result"):
        return "Job not found or not finished", 404

    result = job["result"]
    if fmt == "xlsx":
        path = result.get("xl_path")
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "md":
        path = result.get("md_path")
        mime = "text/markdown"
    else:
        return "Invalid format", 400

    if not path or not os.path.isfile(path):
        return "File not found", 404

    return send_file(path, mimetype=mime, as_attachment=True,
                     download_name=os.path.basename(path))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Web UI for ArcGIS Layer Scanner")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    print(f"\n  Starting web UI at http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
