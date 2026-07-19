"""Web-view report builder: navigable, self-contained, single file.

`econ compile` output: fixed sidebar (chapter nav + live warehouse stats +
filter box), scroll-spy highlighting, a computed State-of-the-World
dashboard landing, auto-generated chapter cards (title/thumb/blurb from each
chapter's own markdown), keyboard navigation, print-safe. Everything —
figures, slider frames, nav JS — inlined; no network, no dependencies.
"""

from __future__ import annotations

import base64
import datetime
import re
from pathlib import Path

import markdown as md

from .config import REPORT
from .model import connect

OUT = REPORT / "world-economy-report.html"


def _chapters() -> list[dict]:
    out = []
    for path in sorted(REPORT.glob("[0-9][0-9]-*.md")):
        text = path.read_text()
        html = md.markdown(text, extensions=["tables", "fenced_code", "toc"])
        m = re.search(r"^# (.+)$", text, re.M)
        title = m.group(1).strip() if m else path.stem
        title = re.sub(r"^Chapter \d+ — ", "", title)
        num = path.stem[:2]
        subs = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html)
        subs = [(sid, re.sub(r"<[^>]+>", "", label)) for sid, label in subs]
        thumb = None
        tm = re.search(r'src="(figures/[^"]+\.png)"', html)
        if tm:
            thumb = tm.group(1)
        pm = re.search(r"<p>(?!<em>)(.*?)</p>", html, re.S)
        blurb = ""
        if pm:
            blurb = re.sub(r"<[^>]+>", "", pm.group(1))
            blurb = re.sub(r"\s+", " ", blurb).strip()[:170]
        out.append({"id": path.stem, "num": num, "title": title, "html": html,
                    "subs": subs, "thumb": thumb, "blurb": blurb})
    return out


def _dashboard_tiles() -> list[tuple[str, str, str]]:
    from .analysis.ch06_synthesis import state_of_the_world

    df = state_of_the_world()
    return list(df.itertuples(index=False, name=None))


def _warehouse_stats() -> dict:
    with connect() as con:
        srcs, series, obs = con.execute(
            "SELECT count(DISTINCT source), count(*), "
            "(SELECT count(*) FROM obs) FROM catalog"
        ).fetchone()
        span = con.execute("SELECT min(year), max(year) FROM obs").fetchone()
    return {"sources": srcs, "series": series, "obs": obs, "span": span}


CSS = """
*{box-sizing:border-box} body{margin:0;font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;
 color:#1f2328;line-height:1.55;background:#fff}
a{color:#1f6feb;text-decoration:none} a:hover{text-decoration:underline}
#layout{display:grid;grid-template-columns:280px 1fr;min-height:100vh}
#sidebar{position:sticky;top:0;height:100vh;overflow-y:auto;background:#0d1117;color:#e6edf3;
 padding:1.1rem .9rem;font-size:.9rem}
#sidebar h1{font-size:1.02rem;margin:.2rem 0 .1rem;color:#fff}
#sidebar .sub{color:#8b949e;font-size:.74rem;margin-bottom:.9rem}
#filter{width:100%;padding:.42rem .6rem;border-radius:6px;border:1px solid #30363d;
 background:#161b22;color:#e6edf3;margin-bottom:.8rem;font-size:.85rem}
#nav a.ch{display:block;padding:.34rem .55rem;border-radius:6px;color:#e6edf3;margin:.1rem 0}
#nav a.ch:hover{background:#161b22;text-decoration:none}
#nav a.ch.active{background:#1f6feb;color:#fff;font-weight:600}
#nav .num{color:#8b949e;font-size:.76rem;margin-right:.45rem}
#nav a.ch.active .num{color:#c9d8ff}
#nav .subs{display:none;margin:.1rem 0 .3rem 1.35rem;border-left:1px solid #30363d;padding-left:.6rem}
#nav li.on .subs{display:block}
#nav .subs a{display:block;color:#8b949e;font-size:.78rem;padding:.14rem 0}
#nav .subs a:hover{color:#e6edf3}
#nav ul{list-style:none;margin:0;padding:0}
#whstats{margin-top:1rem;padding-top:.8rem;border-top:1px solid #30363d;color:#8b949e;font-size:.74rem}
main{padding:2rem 3rem;max-width:980px}
section.chapter{padding-top:.5rem;margin-bottom:3.5rem;border-bottom:2px solid #d0d7de}
img{max-width:100%;border:1px solid #d0d7de;border-radius:6px;margin:.4rem 0}
table{border-collapse:collapse;margin:1rem 0;display:block;overflow-x:auto}
td,th{border:1px solid #d0d7de;padding:.3rem .6rem;font-size:.92rem} th{background:#f6f8fa}
h1{border-bottom:2px solid #d0d7de;padding-bottom:.3rem}
em{color:#57606a}
#dash .tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:.7rem;margin:1rem 0}
#dash .tile{border:1px solid #d0d7de;border-radius:8px;padding:.7rem .8rem;background:#f6f8fa}
#dash .tile b{display:block;font-size:1.25rem;color:#0d1117}
#dash .tile .m{font-size:.78rem;color:#57606a}
#dash .tile .c{font-size:.72rem;color:#8b949e;margin-top:.15rem}
#cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;margin:1.4rem 0}
.card{border:1px solid #d0d7de;border-radius:10px;overflow:hidden;background:#fff;display:block;color:inherit}
.card:hover{border-color:#1f6feb;text-decoration:none;box-shadow:0 3px 10px rgba(31,111,235,.12)}
.card img{border:none;border-radius:0;margin:0;height:140px;width:100%;object-fit:cover}
.card .t{padding:.6rem .8rem .1rem;font-weight:600}
.card .b{padding:0 .8rem .7rem;font-size:.8rem;color:#57606a}
#pn{position:fixed;bottom:1.1rem;right:1.2rem;display:flex;gap:.4rem}
#pn button{border:1px solid #d0d7de;background:#fff;border-radius:8px;padding:.45rem .8rem;
 cursor:pointer;font-size:1rem} #pn button:hover{border-color:#1f6feb;color:#1f6feb}
#burger{display:none}
@media (max-width:900px){#layout{grid-template-columns:1fr}#sidebar{position:fixed;z-index:10;
 width:270px;transform:translateX(-100%);transition:transform .2s}#sidebar.open{transform:none}
 #burger{display:block;position:fixed;top:.7rem;left:.7rem;z-index:11;border:1px solid #d0d7de;
 background:#fff;border-radius:8px;padding:.35rem .6rem;cursor:pointer} main{padding:3rem 1.1rem}}
@media print{#sidebar,#pn,#burger{display:none}#layout{display:block}}
"""

JS = """
const secs=[...document.querySelectorAll('section.chapter,#dash')];
const links={};document.querySelectorAll('#nav a.ch').forEach(a=>links[a.dataset.t]=a);
const obs=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){
 document.querySelectorAll('#nav a.ch').forEach(a=>a.classList.remove('active'));
 document.querySelectorAll('#nav li').forEach(l=>l.classList.remove('on'));
 const a=links[e.target.id];if(a){a.classList.add('active');a.closest('li').classList.add('on');}
}})},{rootMargin:'-8% 0px -80% 0px'});
secs.forEach(s=>obs.observe(s));
document.getElementById('filter').addEventListener('input',ev=>{
 const q=ev.target.value.toLowerCase();
 document.querySelectorAll('#nav li').forEach(li=>{
  li.style.display=li.textContent.toLowerCase().includes(q)?'':'none';});
});
function jump(d){const ids=secs.map(s=>s.id);
 const cur=ids.findIndex(id=>links[id]&&links[id].classList.contains('active'));
 const n=Math.min(Math.max((cur<0?0:cur)+d,0),ids.length-1);
 document.getElementById(ids[n]).scrollIntoView({behavior:'smooth'});}
document.addEventListener('keydown',e=>{if(e.target.tagName!=='INPUT'){
 if(e.key==='ArrowRight')jump(1);if(e.key==='ArrowLeft')jump(-1);}});
const sb=document.getElementById('sidebar');
document.getElementById('burger').addEventListener('click',()=>sb.classList.toggle('open'));
"""


def build() -> Path:
    chapters = _chapters()
    tiles = _dashboard_tiles()
    stats = _warehouse_stats()
    stamp = datetime.date.today().isoformat()

    nav_items = [
        '<li class="on"><a class="ch active" data-t="dash" href="#dash">'
        '<span class="num">◆</span>State of the World</a></li>'
    ]
    for ch in chapters:
        subs = "".join(
            f'<a href="#{sid}">{label}</a>' for sid, label in ch["subs"][:12]
        )
        nav_items.append(
            f'<li><a class="ch" data-t="{ch["id"]}" href="#{ch["id"]}">'
            f'<span class="num">{ch["num"]}</span>{ch["title"]}</a>'
            f'<div class="subs">{subs}</div></li>'
        )

    tile_html = "".join(
        f'<div class="tile"><span class="m">{m}</span><b>{v}</b>'
        f'<div class="c">{c}</div></div>'
        for m, v, c in tiles
    )
    cards = "".join(
        f'<a class="card" href="#{ch["id"]}">'
        + (f'<img src="{ch["thumb"]}" loading="lazy">' if ch["thumb"] else "")
        + f'<div class="t">{ch["num"]} · {ch["title"]}</div>'
        f'<div class="b">{ch["blurb"]}…</div></a>'
        for ch in chapters
    )
    body_sections = "".join(
        f'<section class="chapter" id="{ch["id"]}">{ch["html"]}</section>'
        for ch in chapters
    )

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Economy Lab — Report</title><style>{CSS}</style></head><body>
<button id="burger">☰</button>
<div id="layout">
<aside id="sidebar">
<h1>World Economy Lab</h1>
<div class="sub">compiled {stamp} · every number computed from primary data</div>
<input id="filter" placeholder="filter chapters… ( / )">
<nav id="nav"><ul>{"".join(nav_items)}</ul></nav>
<div id="whstats">warehouse: {stats["sources"]} sources · {stats["series"]:,} series ·
 {stats["obs"]:,} observations · years {stats["span"][0]}–{stats["span"][1]}<br>
 regenerate: <code>econ refresh && econ figures && econ compile</code><br>
 keys: ←/→ chapters</div>
</aside>
<main>
<section id="dash">
<h1>State of the World</h1>
<p><em>Computed live from the warehouse at compile time ({stamp}).</em></p>
<div class="tiles">{tile_html}</div>
<h2>Chapters</h2>
<div id="cards">{cards}</div>
</section>
{body_sections}
</main>
</div>
<div id="pn"><button onclick="jump(-1)">‹</button><button onclick="jump(1)">›</button></div>
<script>{JS}</script>
</body></html>"""

    def embed(match: re.Match) -> str:
        p = REPORT / match.group(1)
        if not p.exists():
            return match.group(0)
        b64 = base64.b64encode(p.read_bytes()).decode()
        return f'src="data:image/png;base64,{b64}"'

    html = re.sub(r'src="(figures/[^"]+)"', embed, html)
    OUT.write_text(html)
    n_ch = len(chapters)
    print(f"compiled web view: {OUT} ({OUT.stat().st_size/1e6:.1f} MB, "
          f"{n_ch} chapters, {len(tiles)} dashboard tiles)")
    return OUT
