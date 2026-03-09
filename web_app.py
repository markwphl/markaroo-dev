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
<title>Government ArcGIS Layer Scanner</title>
<style>
  :root { --bg: #0f172a; --surface: #1e293b; --border: #334155;
          --text: #e2e8f0; --muted: #94a3b8; --accent: #38bdf8;
          --green: #4ade80; --red: #f87171; --yellow: #fbbf24; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh;
         display: flex; flex-direction: column; align-items: center;
         padding: 2rem 1rem; }
  h1 { font-size: 1.6rem; margin-bottom: .25rem; }
  .subtitle { color: var(--muted); font-size: .9rem; margin-bottom: 2rem; }
  .card { background: var(--surface); border: 1px solid var(--border);
          border-radius: .75rem; padding: 1.5rem; width: 100%;
          max-width: 760px; margin-bottom: 1.5rem; }
  label { display: block; font-weight: 600; margin-bottom: .4rem; }
  input[type="url"] { width: 100%; padding: .6rem .8rem; border-radius: .4rem;
          border: 1px solid var(--border); background: var(--bg);
          color: var(--text); font-size: 1rem; }
  input[type="url"]:focus { outline: 2px solid var(--accent); }
  button { padding: .6rem 1.4rem; border: none; border-radius: .4rem;
           font-size: .95rem; cursor: pointer; font-weight: 600;
           transition: opacity .15s; }
  button:hover { opacity: .85; }
  button:disabled { opacity: .4; cursor: not-allowed; }
  .btn-primary { background: var(--accent); color: var(--bg); }
  .btn-download { background: var(--green); color: var(--bg);
                  margin-right: .5rem; margin-top: .5rem; text-decoration: none;
                  display: inline-block; padding: .5rem 1rem; border-radius: .4rem;
                  font-weight: 600; font-size: .9rem; }
  .btn-download:hover { opacity: .85; }
  #progress-box { max-height: 320px; overflow-y: auto; font-family: 'Cascadia Code',
          'Fira Code', monospace; font-size: .82rem; line-height: 1.5;
          background: var(--bg); border: 1px solid var(--border);
          border-radius: .4rem; padding: .8rem; margin-top: 1rem;
          display: none; }
  #progress-box .log { color: var(--muted); }
  #progress-box .stat { color: var(--yellow); }
  #progress-box .error { color: var(--red); }
  #progress-box .done { color: var(--green); font-weight: 700; }
  #summary { display: none; margin-top: 1rem; }
  #summary table { width: 100%; border-collapse: collapse; }
  #summary th, #summary td { text-align: left; padding: .4rem .6rem;
          border-bottom: 1px solid var(--border); }
  #summary th { color: var(--accent); }
  #downloads { display: none; margin-top: 1rem; }
  .spinner { display: inline-block; width: 18px; height: 18px;
             border: 3px solid var(--border); border-top-color: var(--accent);
             border-radius: 50%; animation: spin .7s linear infinite;
             vertical-align: middle; margin-right: .4rem; }
  @keyframes spin { to { transform: rotate(360deg); } }
  #status-line { margin-top: .8rem; font-size: .9rem; color: var(--muted); }
  /* Results table */
  #results-table { display: none; margin-top: 1rem; overflow-x: auto; }
  #results-table table { width: 100%; border-collapse: collapse; font-size: .82rem; }
  #results-table th { background: var(--bg); color: var(--accent); position: sticky; top: 0; }
  #results-table th, #results-table td { padding: .35rem .5rem; border: 1px solid var(--border);
          white-space: nowrap; max-width: 280px; overflow: hidden; text-overflow: ellipsis; }
  #results-table td:nth-child(4) { font-family: monospace; font-size: .75rem; }
</style>
</head>
<body>
  <h1>Government ArcGIS Layer Scanner</h1>
  <p class="subtitle">Find planning &amp; development feature layers from any local government website</p>

  <div class="card">
    <form id="scan-form">
      <label for="url-input">Government Website URL</label>
      <input id="url-input" type="url" name="url" required
             placeholder="https://www.dublinohiousa.gov" autocomplete="url">
      <div style="margin-top:1rem; display:flex; align-items:center;">
        <button type="submit" class="btn-primary" id="scan-btn">Scan</button>
        <span id="status-line"></span>
      </div>
    </form>

    <div id="progress-box"></div>

    <div id="summary">
      <h3 style="margin-bottom:.5rem;">Summary</h3>
      <table><tbody id="summary-body"></tbody></table>
    </div>

    <div id="results-table"></div>

    <div id="downloads"></div>
  </div>

<script>
const form = document.getElementById('scan-form');
const btn = document.getElementById('scan-btn');
const box = document.getElementById('progress-box');
const statusLine = document.getElementById('status-line');
const summaryDiv = document.getElementById('summary');
const summaryBody = document.getElementById('summary-body');
const downloadsDiv = document.getElementById('downloads');
const resultsDiv = document.getElementById('results-table');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = document.getElementById('url-input').value.trim();
  if (!url) return;

  // Reset UI
  box.innerHTML = ''; box.style.display = 'block';
  summaryDiv.style.display = 'none'; summaryBody.innerHTML = '';
  downloadsDiv.style.display = 'none'; downloadsDiv.innerHTML = '';
  resultsDiv.style.display = 'none'; resultsDiv.innerHTML = '';
  btn.disabled = true;
  statusLine.innerHTML = '<span class="spinner"></span> Scanning…';

  // Start scan
  let res;
  try {
    res = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url})
    });
  } catch (err) {
    statusLine.textContent = 'Network error – could not reach server.';
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
    summaryDiv.style.display = 'block';
  });

  evtSource.addEventListener('done', (e) => {
    evtSource.close();
    const data = JSON.parse(e.data);
    statusLine.innerHTML = '<span style="color:var(--green);">&#10003;</span> Scan complete.';
    btn.disabled = false;

    if (data.error) {
      addLine('error', data.error);
      return;
    }

    // Download links
    downloadsDiv.innerHTML = '';
    if (data.xl_file) {
      downloadsDiv.innerHTML += `<a class="btn-download" href="/api/download/${job_id}/xlsx">Download Excel (.xlsx)</a>`;
    }
    if (data.md_file) {
      downloadsDiv.innerHTML += `<a class="btn-download" href="/api/download/${job_id}/md">Download Markdown (.md)</a>`;
    }
    downloadsDiv.style.display = 'block';

    // Build preview table
    if (data.layers && data.layers.length) {
      let html = '<h3 style="margin-bottom:.5rem;">Results Preview</h3>';
      html += '<div style="max-height:300px;overflow:auto;">';
      html += '<table><thead><tr><th>GIS Layer Name</th><th>Source System</th><th>Collection</th><th>API</th><th>Time Period</th><th>Update Frequency</th></tr></thead><tbody>';
      data.layers.forEach(l => {
        html += `<tr><td>${esc(l.layer_name)}</td><td>Esri ArcGIS</td><td>API</td><td title="${esc(l.layer_url)}">${esc(l.layer_url)}</td><td>Current</td><td>Ad Hoc</td></tr>`;
      });
      html += '</tbody></table></div>';
      resultsDiv.innerHTML = html;
      resultsDiv.style.display = 'block';
    }
  });

  evtSource.onerror = () => {
    evtSource.close();
    statusLine.innerHTML = 'Connection lost.';
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
    if not url:
        return jsonify({"error": "URL is required."}), 400

    job_id = uuid.uuid4().hex[:12]
    q: queue.Queue = queue.Queue()
    _jobs[job_id] = {"queue": q, "result": None, "status": "running"}

    def progress_cb(event_type: str, message: str):
        q.put((event_type, message))

    def run():
        try:
            job_output_dir = os.path.join(OUTPUT_DIR, job_id)
            result = scan(url, output_dir=job_output_dir, progress_callback=progress_cb)
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
