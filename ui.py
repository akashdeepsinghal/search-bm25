"""Google-style search UI for the FineWeb Vespa index.

Run:  .venv/bin/python ui.py   then open http://localhost:8000

Vespa Cloud requires mTLS, so the browser can't call it directly;
this tiny server holds the cert and proxies queries (local Docker needs no cert).
"""

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from config import connect_vespa

PAGE_SIZE = 10
SNIPPET_CHARS = 280

app = connect_vespa()  # local Docker or Vespa Cloud, per VESPA_MODE in .env


def make_snippet(text: str, terms: list[str]) -> str:
    """Return a window of text around the first query-term match."""
    text = " ".join(text.split())
    start = 0
    for term in terms:
        m = re.search(re.escape(term), text, re.IGNORECASE)
        if m:
            start = max(0, m.start() - SNIPPET_CHARS // 3)
            break
    snippet = text[start : start + SNIPPET_CHARS]
    return ("… " if start else "") + snippet + (" …" if start + SNIPPET_CHARS < len(text) else "")


def search(q: str, page: int, safe: bool = True) -> dict:
    offset = (page - 1) * PAGE_SIZE
    response = app.query(
        yql="select * from sources * where userQuery()" + (" and adult = false" if safe else ""),
        query=q,
        hits=PAGE_SIZE,
        offset=offset,
        type="weakAnd",
        timeout="5s",
    )
    terms = [t for t in re.findall(r"\w+", q) if len(t) > 1]
    results = []
    for hit in response.hits:
        f = hit["fields"]
        results.append(
            {
                "url": f.get("url", ""),
                "snippet": make_snippet(f.get("text", ""), terms),
                "text": f.get("text", ""),
                "year": f.get("year"),
                "dump": f.get("dump"),
                "token_count": f.get("token_count"),
                "relevance": hit.get("relevance"),
            }
        )
    total = response.json.get("root", {}).get("fields", {}).get("totalCount", len(results))
    return {"total": total, "page": page, "page_size": PAGE_SIZE, "terms": terms, "results": results}


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FineWeb Search</title>
<style>
  :root { --bg:#fff; --fg:#202124; --muted:#4d5156; --link:#1a0dab; --green:#188038; --line:#dfe1e5; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#202124; --fg:#e8eaed; --muted:#bdc1c6; --link:#8ab4f8; --green:#81c995; --line:#5f6368; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.58 arial,sans-serif; }
  header { padding:24px 16px 12px; border-bottom:1px solid var(--line); display:flex; gap:24px; align-items:center; flex-wrap:wrap; }
  header.home { border:0; flex-direction:column; padding-top:18vh; }
  .logo { font:600 28px/1 'Product Sans',arial,sans-serif; letter-spacing:-1px; }
  header.home .logo { font-size:64px; margin-bottom:12px; }
  form { flex:1; min-width:240px; max-width:640px; width:100%; }
  input[type=search] { width:100%; height:46px; padding:0 20px; font-size:16px; color:var(--fg); background:var(--bg);
    border:1px solid var(--line); border-radius:24px; outline:none; }
  input[type=search]:hover, input[type=search]:focus { box-shadow:0 1px 6px rgba(32,33,36,.28); border-color:transparent; }
  main { max-width:652px; margin:0 0 0 16px; padding:0 0 48px; }
  @media (min-width:900px) { main { margin-left:150px; } header:not(.home) { padding-left:150px; } }
  .stats { color:var(--muted); font-size:13px; margin:16px 0 8px; }
  .result { margin:0 0 28px; }
  .result .site { color:var(--green); font-size:12px; line-height:1.3; word-break:break-all; }
  .result a { color:var(--link); font-size:20px; line-height:1.3; text-decoration:none; word-break:break-word; }
  .result a:hover { text-decoration:underline; }
  .result p { margin:3px 0 0; color:var(--muted); }
  .result mark { background:none; color:var(--fg); font-weight:700; }
  .meta { color:var(--muted); font-size:12px; margin-top:2px; display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
  .badge { display:inline-block; padding:1px 8px; border-radius:10px; font-size:11px; font-weight:600; line-height:1.6;
    color:var(--green); border:1px solid var(--green); white-space:nowrap; }
  nav { display:flex; gap:4px; margin-top:8px; flex-wrap:wrap; align-items:center; }
  nav a, nav span { min-width:36px; padding:8px 10px; text-align:center; border-radius:18px; font-size:15px; text-decoration:none; }
  nav a { color:var(--link); }
  nav a:hover { background:var(--line); }
  nav span.cur { background:var(--link); color:var(--bg); font-weight:700; }
  .logo { color:inherit; text-decoration:none; }
  .result { padding:6px 8px; margin-left:-8px; border-radius:8px; }
  .result.active { background:rgba(128,134,139,.12); }
  #preview { display:none; }
  @media (min-width:1250px) {
    #preview.on { display:block; position:fixed; top:96px; bottom:24px; right:24px; left:870px; overflow:auto;
      border:1px solid var(--line); border-radius:12px; padding:16px 20px; }
    #preview .ptitle { color:var(--link); font-size:16px; word-break:break-all; margin-bottom:4px; }
    #preview .pmeta { color:var(--muted); font-size:12px; margin-bottom:12px; }
    #preview .ptext { white-space:pre-wrap; word-break:break-word; line-height:1.6; }
  }
  .safe { display:flex; align-items:center; gap:8px; color:var(--muted); font-size:13px; cursor:pointer; user-select:none; white-space:nowrap; }
  .safe input { position:absolute; opacity:0; }
  .safe .track { width:34px; height:18px; border-radius:9px; background:var(--line); position:relative; transition:background .15s; }
  .safe .track::after { content:''; position:absolute; top:2px; left:2px; width:14px; height:14px; border-radius:50%; background:var(--bg); transition:left .15s; }
  .safe input:checked + .track { background:var(--link); }
  .safe input:checked + .track::after { left:18px; }
  .safe input:focus-visible + .track { outline:2px solid var(--link); outline-offset:2px; }
  header.home .safe { margin-top:4px; }
  .empty, .error { margin-top:24px; color:var(--muted); }
</style></head>
<body>
<header id="head" class="home">
  <a class="logo" href="/">FineWeb</a>
  <form id="f"><input id="q" type="search" placeholder="Search text or paste a URL" autocomplete="off" autofocus></form>
  <label class="safe" title="Hide adult results"><input id="safe" type="checkbox"><span class="track"></span>SafeSearch</label>
</header>
<main id="out"></main>
<aside id="preview"></aside>
<script>
const $ = id => document.getElementById(id);

// SafeSearch: URL param wins, then the saved preference, default on
function initialSafe() {
  const u = new URLSearchParams(location.search).get('safe');
  if (u !== null) return u !== '0';
  try { return localStorage.getItem('safe') !== '0'; } catch { return true; }
}
$('safe').checked = initialSafe();
const safeFlag = () => $('safe').checked ? '1' : '0';
const esc = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const reEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function highlight(text, terms) {
  const safe = esc(text);
  if (!terms.length) return safe;
  const re = new RegExp('(' + terms.map(t => reEsc(esc(t))).join('|') + ')', 'gi');
  return safe.replace(re, '<mark>$1</mark>');
}

function pager(page, pages) {
  if (pages <= 1) return '';
  const start = Math.max(1, Math.min(page - 4, pages - 9)), end = Math.min(pages, start + 9);
  let h = '<nav>';
  if (page > 1) h += '<a href="#" data-p="' + (page - 1) + '">‹ Prev</a>';
  for (let i = start; i <= end; i++)
    h += i === page ? '<span class="cur">' + i + '</span>' : '<a href="#" data-p="' + i + '">' + i + '</a>';
  if (page < pages) h += '<a href="#" data-p="' + (page + 1) + '">Next ›</a>';
  return h + '</nav>';
}

function showPreview(results, terms, i) {
  const x = results[i], el = $('preview');
  document.querySelectorAll('.result').forEach(r => r.classList.toggle('active', +r.dataset.i === i));
  el.innerHTML = '<div class="ptitle">' + esc(x.url) + '</div>' +
    '<div class="meta" style="margin-bottom:12px">' + metaHtml(x) + '</div>' +
    '<div class="ptext">' + highlight(x.text, terms) + '</div>';
  el.scrollTop = 0;
  el.classList.add('on');
}

function metaHtml(x) {
  const parts = [x.year, x.dump, x.token_count ? x.token_count.toLocaleString() + ' tokens' : null].filter(Boolean).join(' · ');
  const badge = x.relevance == null ? '' : '<span class="badge" title="Vespa relevance score (bm25)">★ ' + x.relevance.toFixed(2) + '</span>';
  return badge + (parts ? '<span>' + parts + '</span>' : '');
}

function prettyUrl(u) {
  try { const x = new URL(u); return esc(x.hostname + (x.pathname === '/' ? '' : x.pathname.replace(/\//g, ' › '))); }
  catch { return esc(u); }
}

async function run(q, page) {
  $('head').classList.remove('home');
  $('q').value = q;
  $('out').innerHTML = '<div class="empty">Searching…</div>'; $('preview').classList.remove('on');
  history.replaceState(null, '', '?q=' + encodeURIComponent(q) + '&page=' + page + '&safe=' + safeFlag());
  document.title = q + ' - FineWeb Search';
  try {
    const r = await fetch('/api/search?q=' + encodeURIComponent(q) + '&page=' + page + '&safe=' + safeFlag());
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    if (!d.results.length) { $('out').innerHTML = '<div class="empty">No results for <b>' + esc(q) + '</b>.</div>'; return; }
    const pages = Math.ceil(d.total / d.page_size);
    $('out').innerHTML =
      '<div class="stats">About ' + d.total.toLocaleString() + ' results</div>' +
      d.results.map((x, i) =>
        '<div class="result" data-i="' + i + '"><div class="site">' + prettyUrl(x.url) + '</div>' +
        '<a href="' + esc(x.url) + '" target="_blank" rel="noopener noreferrer">' + esc(x.url) + '</a>' +
        '<p>' + highlight(x.snippet, d.terms) + '</p>' +
        '<div class="meta">' + metaHtml(x) + '</div></div>'
      ).join('') +
      pager(page, pages);
    showPreview(d.results, d.terms, 0);
    $('out').querySelectorAll('.result').forEach(el => el.onmouseenter = () => showPreview(d.results, d.terms, +el.dataset.i));
    $('out').querySelectorAll('nav a').forEach(a => a.onclick = e => { e.preventDefault(); run(q, +a.dataset.p); window.scrollTo(0, 0); });
  } catch (e) {
    $('out').innerHTML = '<div class="error">Search failed: ' + esc(String(e.message || e)) + '</div>';
  }
}

$('safe').onchange = () => {
  try { localStorage.setItem('safe', safeFlag()); } catch {}
  const q = $('q').value.trim();
  if (q) run(q, 1);
};
$('f').onsubmit = e => { e.preventDefault(); const q = $('q').value.trim(); if (q) run(q, 1); };
const p = new URLSearchParams(location.search);
if (p.get('q')) run(p.get('q'), Math.max(1, +p.get('page') || 1));
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif url.path == "/api/search":
            params = parse_qs(url.query)
            q = params.get("q", [""])[0].strip()
            try:
                page = max(1, int(params.get("page", ["1"])[0]))
                safe = params.get("safe", ["1"])[0] != "0"
                payload, status = search(q, page, safe), 200
            except Exception as e:  # surface Vespa/network errors to the UI
                payload, status = {"error": str(e)}, 500
            self._send(status, json.dumps(payload).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    print("Serving on http://localhost:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
