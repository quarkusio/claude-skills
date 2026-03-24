#!/usr/bin/env python3
"""
Rich browser-based git diff viewer with sidebar file tree.

Usage:
  diff-view.py [options] [-- git-diff-args...]

Modes:
  (default)              Unstaged changes
  --staged               Staged changes
  --branch <name>        Compare current branch to <name>
  --commit <ref>         Show a commit or range (e.g. HEAD~3, abc123)
  --watch                Live-updating diff via local HTTP server
  --summary <text>       AI-generated summary (optional, shown in sidebar)

Examples:
  diff-view.py                          # unstaged changes
  diff-view.py --staged                 # staged changes
  diff-view.py --branch main            # current branch vs main
  diff-view.py --commit HEAD~3          # last 3 commits
  diff-view.py --watch                  # live-updating unstaged diff
  diff-view.py --watch --branch main    # live-updating branch diff

Watch mode API:
  POST /api/summary  {"summary": "AI text"}  - update the sidebar summary
  GET  /api/update                            - poll for diff changes
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler


def get_branch():
    return subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()


def get_git_diff(args):
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    return result.stdout


def parse_numstat(args):
    result = subprocess.run(
        ["git"] + args + ["--numstat"], capture_output=True, text=True
    )
    files = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            added = int(parts[0]) if parts[0] != "-" else 0
            removed = int(parts[1]) if parts[1] != "-" else 0
            files.append({"path": parts[2], "added": added, "removed": removed})
    return files


def get_file_statuses(args):
    result = subprocess.run(
        ["git"] + args + ["--name-status"], capture_output=True, text=True
    )
    statuses = {}
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        statuses[parts[-1]] = parts[0][0]
    return statuses


def build_meta(branch, title, diff_args, summary=None):
    files = parse_numstat(diff_args)
    statuses = get_file_statuses(diff_args)
    for f in files:
        f["status"] = statuses.get(f["path"], "M")
    if summary is None:
        n = len(files)
        a = sum(f["added"] for f in files)
        r = sum(f["removed"] for f in files)
        summary = f"{n} files changed with {a} additions and {r} deletions."
    return {"title": title, "branch": branch, "summary": summary, "files": files}


def run_diff2html(diff_text, title):
    result = subprocess.run(
        ["diff2html", "-i", "stdin", "-s", "side", "-o", "stdout", "--title", title],
        input=diff_text, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"diff2html error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


# ─── Shared CSS ────────────────────────────────────────────────────────────────

SIDEBAR_STYLES = '''
      body {
        margin: 0 !important;
        padding: 0 !important;
        text-align: left !important;
      }
      .enriched-layout {
        display: flex !important;
        min-height: 100vh;
      }
      .enriched-sidebar {
        width: 380px; min-width: 380px; max-width: 380px;
        background: #161b22;
        border-right: 1px solid #30363d;
        padding: 20px;
        overflow-y: auto;
        position: fixed; top: 0; left: 0; height: 100vh;
        box-sizing: border-box;
        z-index: 9999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        transition: transform 0.25s ease;
      }
      .enriched-sidebar.collapsed { transform: translateX(-100%); }
      .enriched-main {
        margin-left: 380px; flex: 1; min-width: 0;
        transition: margin-left 0.25s ease;
      }
      .enriched-main.expanded { margin-left: 0; }
      .enriched-main > * { text-align: left !important; }
      .es-toggle-btn {
        position: absolute; top: 8px; right: 8px;
        width: 28px; height: 28px;
        background: #30363d; border: 1px solid #484f58; border-radius: 4px;
        color: #8b949e; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        font-size: 16px; line-height: 1; padding: 0; z-index: 10000;
        transition: background 0.15s ease;
      }
      .es-toggle-btn:hover { background: #484f58; color: #c9d1d9; }
      .es-open-btn {
        position: fixed; top: 8px; left: 8px;
        width: 32px; height: 32px;
        background: #161b22; border: 1px solid #30363d; border-radius: 6px;
        color: #8b949e; cursor: pointer;
        display: none; align-items: center; justify-content: center;
        font-size: 18px; line-height: 1; padding: 0; z-index: 10000;
        transition: background 0.15s ease;
      }
      .es-open-btn:hover { background: #30363d; color: #c9d1d9; }
      .es-open-btn.visible { display: flex; }
      .es-section-title {
        margin: 0 0 10px 0; font-size: 11px; font-weight: 600;
        color: #8b949e; text-transform: uppercase; letter-spacing: 0.8px;
      }
      .es-summary {
        font-size: 13px; line-height: 1.6; color: #c9d1d9;
        margin: 0 0 20px 0; padding-bottom: 16px;
        border-bottom: 1px solid #30363d;
      }
      .es-summary code {
        background: #30363d; padding: 1px 5px; border-radius: 3px; font-size: 12px;
      }
      .es-summary-loading {
        color: #8b949e; font-style: italic;
      }
      .es-stats {
        display: flex; gap: 12px; margin-bottom: 16px; padding-bottom: 12px;
        border-bottom: 1px solid #30363d; font-size: 12px; font-weight: 500; color: #8b949e;
      }
      .es-tree {
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', Menlo, monospace;
        font-size: 12px; line-height: 1.4; color: #8b949e;
      }
      .es-tree ul { list-style: none; margin: 0; padding: 0; }
      .es-tree li { position: relative; padding-left: 20px; }
      .es-tree li::before {
        content: ''; position: absolute; left: 6px; top: 0;
        height: 100%; border-left: 1px solid #30363d;
      }
      .es-tree li::after {
        content: ''; position: absolute; left: 6px; top: 11px;
        width: 10px; border-bottom: 1px solid #30363d;
      }
      .es-tree li:last-child::before { height: 11px; }
      .es-tree > ul > li::before, .es-tree > ul > li::after { display: none; }
      .es-tree > ul > li { padding-left: 0; }
      .es-tree .es-node { display: inline-block; padding: 2px 0; white-space: nowrap; }
      .es-tree .es-dir { color: #58a6ff; cursor: default; }
      .es-tree .es-file { color: #c9d1d9; }
      .es-tree .es-badge {
        display: inline-block; font-size: 10px; font-weight: 600;
        padding: 0 4px; border-radius: 3px; margin-right: 4px;
        line-height: 16px; vertical-align: middle;
      }
      .es-badge-M { background: #d29922; color: #0d1117; }
      .es-badge-A { background: #3fb950; color: #0d1117; }
      .es-badge-D { background: #f85149; color: #0d1117; }
      .es-badge-R { background: #58a6ff; color: #0d1117; }
      .es-tree .es-stats-inline { color: #6e7681; font-size: 11px; margin-left: 6px; }
      .es-tree .es-stats-inline .es-add { color: #3fb950; }
      .es-tree .es-stats-inline .es-del { color: #f85149; }
      .es-watch-badge {
        display: inline-block; background: #238636; color: #fff;
        font-size: 10px; font-weight: 600; padding: 2px 6px;
        border-radius: 4px; margin-left: 8px; letter-spacing: 0.5px;
      }
      .es-update-flash { animation: es-flash 0.3s ease; }
      @keyframes es-flash { 0% { opacity: 0.6; } 100% { opacity: 1; } }
'''

# ─── Shared JS functions ──────────────────────────────────────────────────────

SIDEBAR_JS_FUNCTIONS = '''
      function buildTree(files) {
        var tree = {};
        files.forEach(function(f) {
          var parts = f.path.split('/');
          var node = tree;
          for (var i = 0; i < parts.length - 1; i++) {
            if (!node[parts[i]]) node[parts[i]] = {};
            node = node[parts[i]];
          }
          node[parts[parts.length - 1]] = f;
        });
        return tree;
      }

      function collapseTree(tree) {
        var result = {};
        Object.keys(tree).forEach(function(name) {
          var value = tree[name];
          if (typeof value === 'object' && !value.status) {
            var chain = [name];
            var node = value;
            while (true) {
              var keys = Object.keys(node);
              if (keys.length === 1) {
                var childVal = node[keys[0]];
                if (typeof childVal === 'object' && !childVal.status) {
                  chain.push(keys[0]);
                  node = childVal;
                  continue;
                }
              }
              break;
            }
            result[chain.join('/')] = collapseTree(node);
          } else {
            result[name] = value;
          }
        });
        return result;
      }

      function renderTree(tree) {
        var ul = document.createElement('ul');
        Object.keys(tree).forEach(function(name) {
          var value = tree[name];
          var li = document.createElement('li');
          var span = document.createElement('span');
          span.className = 'es-node';
          if (typeof value === 'object' && !value.status) {
            span.innerHTML = '<span class="es-dir">' + escapeHtml(name) + '/</span>';
            li.appendChild(span);
            li.appendChild(renderTree(value));
          } else {
            var badge = '<span class="es-badge es-badge-' + value.status + '">' + value.status + '</span>';
            var stats = '';
            if (value.added || value.removed) {
              var parts = [];
              if (value.added) parts.push('<span class="es-add">+' + value.added + '</span>');
              if (value.removed) parts.push('<span class="es-del">-' + value.removed + '</span>');
              stats = '<span class="es-stats-inline">' + parts.join(' ') + '</span>';
            }
            span.innerHTML = badge + '<span class="es-file">' + escapeHtml(name) + '</span>' + stats;
            li.appendChild(span);
          }
          ul.appendChild(li);
        });
        return ul;
      }

      function escapeHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
      }

      function buildSidebar(meta, watching) {
        var sidebar = document.createElement('div');
        sidebar.className = 'enriched-sidebar';
        sidebar.id = 'es-sidebar';

        var closeBtn = document.createElement('button');
        closeBtn.className = 'es-toggle-btn';
        closeBtn.innerHTML = '&#x2715;';
        closeBtn.title = 'Close sidebar';
        sidebar.appendChild(closeBtn);

        var h3sum = document.createElement('h3');
        h3sum.className = 'es-section-title';
        h3sum.textContent = 'Summary';
        sidebar.appendChild(h3sum);
        var psum = document.createElement('p');
        psum.className = 'es-summary';
        psum.id = 'es-summary-text';
        if (meta.summary) {
          psum.innerHTML = meta.summary;
        } else {
          psum.innerHTML = '<span class="es-summary-loading">Generating summary...</span>';
        }
        sidebar.appendChild(psum);

        var totalAdded = 0, totalRemoved = 0;
        meta.files.forEach(function(f) { totalAdded += (f.added || 0); totalRemoved += (f.removed || 0); });
        var statsDiv = document.createElement('div');
        statsDiv.className = 'es-stats';
        statsDiv.id = 'es-stats-bar';
        statsDiv.innerHTML = '<span>' + meta.files.length + ' files</span> '
          + '<span style="color:#3fb950">+' + totalAdded + '</span> '
          + '<span style="color:#f85149">-' + totalRemoved + '</span>';
        sidebar.appendChild(statsDiv);

        var h3tree = document.createElement('h3');
        h3tree.className = 'es-section-title';
        h3tree.textContent = 'Files Changed';
        if (watching) {
          var watchBadge = document.createElement('span');
          watchBadge.className = 'es-watch-badge';
          watchBadge.textContent = 'LIVE';
          h3tree.appendChild(watchBadge);
        }
        sidebar.appendChild(h3tree);

        var treeContainer = document.createElement('div');
        treeContainer.className = 'es-tree';
        treeContainer.id = 'es-tree-container';
        var tree = buildTree(meta.files);
        var collapsed = collapseTree(tree);
        treeContainer.appendChild(renderTree(collapsed));
        sidebar.appendChild(treeContainer);

        return { sidebar: sidebar, closeBtn: closeBtn };
      }

      function setupLayout(meta, watching) {
        var result = buildSidebar(meta, watching);
        var sidebar = result.sidebar;
        var closeBtn = result.closeBtn;

        var mainDiv = document.createElement('div');
        mainDiv.className = 'enriched-main';
        mainDiv.id = 'es-main-content';
        while (document.body.firstChild) {
          mainDiv.appendChild(document.body.firstChild);
        }

        var openBtn = document.createElement('button');
        openBtn.className = 'es-open-btn';
        openBtn.id = 'es-open-btn';
        openBtn.innerHTML = '&#9776;';
        openBtn.title = 'Open sidebar';

        closeBtn.addEventListener('click', function() {
          sidebar.classList.add('collapsed');
          mainDiv.classList.add('expanded');
          openBtn.classList.add('visible');
        });
        openBtn.addEventListener('click', function() {
          sidebar.classList.remove('collapsed');
          mainDiv.classList.remove('expanded');
          openBtn.classList.remove('visible');
        });

        var wrapper = document.createElement('div');
        wrapper.className = 'enriched-layout';
        wrapper.appendChild(sidebar);
        wrapper.appendChild(mainDiv);
        document.body.appendChild(wrapper);
        document.body.appendChild(openBtn);
      }
'''


# ─── Static mode ───────────────────────────────────────────────────────────────

def _build_static_injection(meta_json, watching=False):
    return f'''
    <style>{SIDEBAR_STYLES}</style>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
      var META = {meta_json};
      {SIDEBAR_JS_FUNCTIONS}
      setupLayout(META, {'true' if watching else 'false'});
    }});
    </script>
    '''


def enrich_html(diff_html, meta, watching=False):
    meta_json = json.dumps(meta)
    injection = _build_static_injection(meta_json, watching)
    head_close = diff_html.find("</head>")
    if head_close > 0:
        return diff_html[:head_close] + injection + diff_html[head_close:]
    return injection + diff_html


def generate(diff_args, title, branch, summary=None, output_file=None):
    diff_text = get_git_diff(diff_args)
    if not diff_text.strip():
        return None
    full_title = f"[{branch}] {title}"
    diff_html = run_diff2html(diff_text, full_title)
    meta = build_meta(branch, title, diff_args, summary)
    enriched = enrich_html(diff_html, meta)
    if output_file is None:
        output_file = "/tmp/claude-diff-view.html"
    with open(output_file, "w") as f:
        f.write(enriched)
    return output_file


# ─── Watch mode ────────────────────────────────────────────────────────────────

def _extract_diff_body(diff_html):
    """Extract body content from diff2html HTML, keeping the <h1> title."""
    body_match = re.search(r'<body[^>]*>(.*)</body>', diff_html, re.DOTALL)
    return body_match.group(1) if body_match else diff_html


def _build_watch_page(title):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{SIDEBAR_STYLES}</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css"
      media="screen and (prefers-color-scheme: light)" />
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css"
      media="screen and (prefers-color-scheme: dark)" />
</head>
<body style="background: rgb(13,17,23); color: #e6edf3;">
<div id="diff-placeholder" style="text-align:center; padding:60px; color:#8b949e; font-family:sans-serif;">
  Loading diff...
</div>

<script>
{SIDEBAR_JS_FUNCTIONS}

var currentHash = null;
var currentSummary = null;
var layoutReady = false;

function initDiff2HtmlUI(container) {{
  // Re-run diff2html UI features (Viewed checkbox, file toggle, etc.)
  if (window.Diff2HtmlUI) {{
    var target = container || document.getElementById('es-main-content');
    if (target) {{
      var ui = new Diff2HtmlUI(target);
      ui.fileContentToggle();
      ui.fileListToggle(false);
      ui.synchronisedScroll();
      ui.highlightCode();
    }}
  }}
}}

function updateSidebar(meta) {{
  var sumEl = document.getElementById('es-summary-text');
  if (sumEl) sumEl.innerHTML = meta.summary || '<span class="es-summary-loading">Generating summary...</span>';

  var totalAdded = 0, totalRemoved = 0;
  meta.files.forEach(function(f) {{ totalAdded += (f.added || 0); totalRemoved += (f.removed || 0); }});
  var statsEl = document.getElementById('es-stats-bar');
  if (statsEl) {{
    statsEl.innerHTML = '<span>' + meta.files.length + ' files</span> '
      + '<span style="color:#3fb950">+' + totalAdded + '</span> '
      + '<span style="color:#f85149">-' + totalRemoved + '</span>';
  }}

  var treeEl = document.getElementById('es-tree-container');
  if (treeEl) {{
    treeEl.innerHTML = '';
    var tree = buildTree(meta.files);
    var collapsed = collapseTree(tree);
    treeEl.appendChild(renderTree(collapsed));
  }}
}}

function poll() {{
  fetch('/api/update')
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      // Check for async summary updates even if diff hasn't changed
      if (data.ai_summary && data.ai_summary !== currentSummary) {{
        currentSummary = data.ai_summary;
        var sumEl = document.getElementById('es-summary-text');
        if (sumEl) {{
          sumEl.innerHTML = data.ai_summary;
          sumEl.classList.add('es-update-flash');
          setTimeout(function() {{ sumEl.classList.remove('es-update-flash'); }}, 300);
        }}
      }}

      if (data.hash === currentHash) return;
      currentHash = data.hash;

      if (!layoutReady) {{
        var placeholder = document.getElementById('diff-placeholder');
        if (placeholder) placeholder.remove();

        if (data.diff_styles) {{
          var styleEl = document.createElement('style');
          styleEl.textContent = data.diff_styles;
          document.head.appendChild(styleEl);
        }}

        var bodyDiv = document.createElement('div');
        bodyDiv.innerHTML = data.diff_body;
        while (bodyDiv.firstChild) {{
          document.body.appendChild(bodyDiv.firstChild);
        }}

        // Use AI summary if available, otherwise use meta summary
        var meta = data.meta;
        if (data.ai_summary) {{
          meta = Object.assign({{}}, meta, {{ summary: data.ai_summary }});
          currentSummary = data.ai_summary;
        }}
        setupLayout(meta, true);
        layoutReady = true;

        if (data.diff_scripts) {{
          var scriptDiv = document.createElement('div');
          scriptDiv.innerHTML = data.diff_scripts;
          var scripts = scriptDiv.querySelectorAll('script');
          scripts.forEach(function(s) {{
            var ns = document.createElement('script');
            if (s.src) ns.src = s.src;
            else ns.textContent = s.textContent;
            document.head.appendChild(ns);
          }});
          // Wait for scripts to load, then init diff2html UI features
          setTimeout(function() {{ initDiff2HtmlUI(); }}, 500);
        }}
      }} else {{
        var mainEl = document.getElementById('es-main-content');
        if (mainEl) {{
          var scrollTop = mainEl.scrollTop;
          mainEl.innerHTML = data.diff_body;
          mainEl.scrollTop = scrollTop;
          mainEl.classList.add('es-update-flash');
          setTimeout(function() {{ mainEl.classList.remove('es-update-flash'); }}, 300);
          initDiff2HtmlUI(mainEl);
        }}
        var meta = data.meta;
        if (data.ai_summary) meta = Object.assign({{}}, meta, {{ summary: data.ai_summary }});
        updateSidebar(meta);
      }}
    }})
    .catch(function(e) {{
      console.error('Poll error:', e);
    }});
}}

poll();
setInterval(poll, 2000);
</script>
</body>
</html>'''


class WatchState:
    def __init__(self, diff_args, title, branch, summary):
        self.diff_args = diff_args
        self.title = title
        self.branch = branch
        self.summary = summary
        self.ai_summary = None  # Set via POST /api/summary
        self.current_hash = None
        self.current_data = None
        self.lock = threading.Lock()
        self.refresh()

    def set_ai_summary(self, text):
        with self.lock:
            self.ai_summary = text

    def refresh(self):
        diff_text = get_git_diff(self.diff_args)
        diff_hash = hashlib.md5(diff_text.encode()).hexdigest()

        with self.lock:
            if diff_hash == self.current_hash:
                return False

            self.current_hash = diff_hash

            if not diff_text.strip():
                self.current_data = {
                    "hash": diff_hash,
                    "meta": {"title": self.title, "branch": self.branch,
                             "summary": "No changes.", "files": []},
                    "diff_body": "<p style='text-align:center;color:#8b949e;padding:40px'>No changes to show.</p>",
                    "diff_styles": "", "diff_scripts": "",
                }
                return True

            full_title = f"[{self.branch}] {self.title}"
            diff_html = run_diff2html(diff_text, full_title)
            meta = build_meta(self.branch, self.title, self.diff_args, self.summary)

            diff_body = _extract_diff_body(diff_html)
            styles = "\n".join(re.findall(r'<style[^>]*>(.*?)</style>', diff_html, re.DOTALL))
            scripts = "\n".join(re.findall(r'<script[^>]*>.*?</script>', diff_html, re.DOTALL))

            self.current_data = {
                "hash": diff_hash,
                "meta": meta,
                "diff_body": diff_body,
                "diff_styles": styles,
                "diff_scripts": scripts,
            }
            return True


def make_handler(state, page_html):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(page_html.encode())
            elif self.path == '/api/update':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                with state.lock:
                    data = dict(state.current_data or {})
                    data["ai_summary"] = state.ai_summary
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == '/api/summary':
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body)
                    state.set_ai_summary(payload.get("summary", ""))
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                except Exception as e:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(str(e).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    return Handler


def find_free_port():
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def watch_server(diff_args, title, branch, summary):
    port = find_free_port()
    state = WatchState(diff_args, title, branch, summary)

    full_title = f"[{branch}] {title}"
    page_html = _build_watch_page(full_title)

    handler_class = make_handler(state, page_html)
    server = HTTPServer(('127.0.0.1', port), handler_class)

    parent_pid = os.getppid()

    def refresh_loop():
        while True:
            time.sleep(2)
            # Stop if parent process (Claude) has exited
            try:
                os.kill(parent_pid, 0)
            except OSError:
                print("\nParent process exited. Shutting down.", flush=True)
                server.shutdown()
                return
            state.refresh()

    refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
    refresh_thread.start()

    url = f"http://127.0.0.1:{port}"
    print(f"Watch server at {url} (PID {os.getpid()})")
    print(f"POST summary: curl -X POST {url}/api/summary -d '{{\"summary\":\"...\"}}'")
    print("Stops automatically when Claude session exits.")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped watching.")
        server.shutdown()


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Rich browser-based git diff viewer")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--branch", type=str)
    parser.add_argument("--commit", type=str)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--summary", type=str, default=None)
    parser.add_argument("--output", type=str, default="/tmp/claude-diff-view.html")
    parser.add_argument("extra", nargs="*")

    args = parser.parse_args()
    branch = get_branch()

    if args.staged:
        diff_args = ["diff", "--staged"]
        title = "Staged Changes"
    elif args.branch:
        diff_args = ["diff", f"{args.branch}...HEAD"]
        title = f"Changes vs {args.branch}"
    elif args.commit:
        ref = args.commit
        if ref.startswith("HEAD~") or ref.startswith("HEAD^"):
            diff_args = ["diff", f"{ref}..HEAD"]
            title = f"Last {ref.replace('HEAD~', '')} commits"
        else:
            diff_args = ["show", ref]
            msg = subprocess.check_output(
                ["git", "log", "-1", "--format=%s", ref], text=True
            ).strip()
            short_sha = subprocess.check_output(
                ["git", "rev-parse", "--short", ref], text=True
            ).strip()
            title = f"{short_sha} \u2014 {msg}"
    elif args.extra:
        diff_args = ["diff"] + args.extra
        title = "Diff"
    else:
        diff_args = ["diff"]
        title = "Unstaged Changes"

    if args.watch:
        watch_server(diff_args, title, branch, args.summary)
    else:
        result = generate(diff_args, title, branch, args.summary, output_file=args.output)
        if result:
            webbrowser.open(f"file://{os.path.abspath(result)}")
            print(f"Opened {result}")
        else:
            print("No changes to show.")


if __name__ == "__main__":
    main()
