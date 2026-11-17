#!/usr/bin/env python3
"""Build every page of the Aethelon Global site from the files in content/.

    python3 build.py

- Blog posts:     content/posts/<slug>.md        -> /insights/<slug>/
- Stories:        content/stories/<slug>.md      -> /stories/<slug>/
- Services:       content/services.json          -> /services/ and /services/<slug>/
- Industries:     content/industries.json        -> /industries/ and /industries/<slug>/
- Careers:        content/careers.json           -> /careers/ and /careers/<slug>/
- Company info:   content/site.json              -> header, footer, contact, about
The home page (index.html) keeps its hand-built sections; this script refreshes its
header, footer and "stories & insights" feed between the BUILD markers.
Only the Python standard library is used.
"""
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
C = ROOT / "content"
esc = html.escape

SITE = json.loads((C / "site.json").read_text())
SERVICES = json.loads((C / "services.json").read_text())
INDUSTRIES = json.loads((C / "industries.json").read_text())
CAREERS = json.loads((C / "careers.json").read_text())
SVC = {s["slug"]: s for s in SERVICES}
IND = {i["slug"]: i for i in INDUSTRIES}
PALETTE = [("#076189", "#fe7826"), ("#4d9637", "#0b3d63"), ("#068e9b", "#db401e"), ("#fe7826", "#0b3d63"),
           ("#be321e", "#fe7826"), ("#0b3d63", "#068e9b"), ("#ef5b22", "#4d9637")]
LOGO_TILES = [("A", "#fe7826"), ("E", "#ef5b22"), ("T", "#db401e"), ("H", "#be321e"),
              ("E", "#0b3d63"), ("L", "#076189"), ("O", "#068e9b"), ("N", "#4d9637")]
PAGES = []  # (url, title, type, summary, text) for search + sitemap


# ---------------------------------------------------------------- markdown

def inline(t):
    t = esc(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}"' + (' rel="noopener" target="_blank"' if m.group(2).startswith("http") else "") + f">{m.group(1)}</a>", t)
    return t


def md(src):
    out, para, lst = [], [], None

    def flush():
        nonlocal para, lst
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para = []
        if lst:
            tag, items = lst
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>")
            lst = None

    for raw in src.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush(); continue
        if line.startswith("### "):
            flush(); out.append(f"<h3>{inline(line[4:])}</h3>"); continue
        if line.startswith("## "):
            flush(); h = line[3:].strip(); out.append(f'<h2 id="{slugify(h)}">{inline(h)}</h2>'); continue
        if line.startswith("> "):
            flush(); out.append(f"<blockquote><p>{inline(line[2:])}</p></blockquote>"); continue
        m = re.match(r"^\s*[-*] (.*)", line)
        n = re.match(r"^\s*\d+[.)] (.*)", line)
        if m or n:
            if para:
                out.append(f"<p>{inline(' '.join(para))}</p>"); para = []
            tag = "ul" if m else "ol"
            if not lst or lst[0] != tag:
                if lst:
                    flush()
                lst = (tag, [])
            lst[1].append((m or n).group(1)); continue
        if lst and raw.startswith("  "):
            lst[1][-1] += " " + line.strip(); continue
        if lst:
            flush()
        para.append(line.strip())
    flush()
    return "\n".join(out)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def plain(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def read_md_dir(folder):
    items = []
    for f in sorted((C / folder).glob("*.md")):
        text = f.read_text()
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        if not m:
            raise SystemExit(f"{f}: missing --- frontmatter ---")
        meta = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        meta["slug"] = meta.get("slug") or f.stem
        meta["body"] = m.group(2).strip()
        meta["html"] = md(meta["body"])
        meta["readtime"] = int(meta.get("readtime") or max(1, round(len(meta["body"].split()) / 220)))
        items.append(meta)
    return sorted(items, key=lambda x: x.get("date", ""), reverse=True)


POSTS = read_md_dir("posts")
STORIES = read_md_dir("stories")
POST = {p["slug"]: p for p in POSTS}
STORY = {s["slug"]: s for s in STORIES}


def nice_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return d


# ---------------------------------------------------------------- theme helpers

TILE_COLORS = ["#fe7826", "#ef5b22", "#db401e", "#be321e", "#0b3d63", "#076189", "#068e9b", "#4d9637"]
DARK_TEXT_ON = {"#fe7826", "#ef5b22"}  # light tiles get dark text


def tile_color(i):
    c = TILE_COLORS[i % len(TILE_COLORS)]
    return c, ("#06192b" if c in DARK_TEXT_ON else "#ffffff")


def abbr(name):
    words = [w for w in re.split(r"[^A-Za-z]+", name) if w and w.lower() not in ("and", "the", "of")]
    if len(words) >= 2:
        return words[0][0].upper() + words[1][0].lower()
    return (words[0][:2]).capitalize() if words else "?"


for i, s in enumerate(SERVICES):
    s["abbr"] = {"ai-strategy": "Ai"}.get(s["slug"], abbr(s["name"]))
    s["color"], s["text_color"] = tile_color(i)
for i, x in enumerate(INDUSTRIES):
    x["abbr"] = abbr(x["name"])
    x["color"], x["text_color"] = tile_color(i + 3)

ARR = ('<svg class="arr" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="12" fill="currentColor"/>'
       '<path d="M7 12h9m-4-4 4 4-4 4" stroke="var(--arr-ink, #fff)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def btn(label, href, cls="", arrow=True, extra=""):
    return f'<a class="btn {cls}" href="{href}"{extra}>{esc(label)}{(" " + ARR) if arrow else ""}</a>'


def tile(item, href=None, size=""):
    attrs = f'style="--t:{item["color"]};--tt:{item["text_color"]}" title="{esc(item["name"])}"'
    if href:
        return f'<a class="tile {size}" href="{href}" {attrs} aria-label="{esc(item["name"])}">{esc(item["abbr"])}</a>'
    return f'<span class="tile {size}" {attrs} aria-hidden="true">{esc(item["abbr"])}</span>'


def tiles_block(items, base, cols=5):
    return f'<div class="tiles" style="--cols:{cols}">' + "".join(tile(x, f"/{base}/{x['slug']}/") for x in items) + "</div>"


# ---------------------------------------------------------------- shared chrome

def logo(light=False):
    tiles = "".join(f'<span style="--t:{c}">{l}</span>' for l, c in LOGO_TILES)
    return (f'<a href="/" class="logo{" light" if light else ""}" aria-label="{esc(SITE["name"])} home"><span class="logo-tiles" aria-hidden="true" translate="no">{tiles}</span>'
            f'<span class="logo-sub" aria-hidden="true" translate="no">Global</span></a>')


CHEV = '<svg class="chev" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 4l4 4 4-4"/></svg>'


UJ = ('<rect width="36" height="24" fill="#012169"/><path d="M0 0L36 24M36 0L0 24" stroke="#fff" stroke-width="4.8"/>'
      '<path d="M0 0L36 24M36 0L0 24" stroke="#C8102E" stroke-width="1.6"/><path d="M18 0v24M0 12h36" stroke="#fff" stroke-width="8"/>'
      '<path d="M18 0v24M0 12h36" stroke="#C8102E" stroke-width="4.8"/>')
FLAGS = {
    "gb": UJ,
    "za": '<rect width="36" height="24" fill="#fff"/><rect width="36" height="8" fill="#E03C31"/><rect y="16" width="36" height="8" fill="#001489"/><path d="M0 0L14 12L0 24Z" fill="#007749"/><path d="M0 3L11 12L0 21" fill="none" stroke="#FFB81C" stroke-width="1.6"/><path d="M0 4.5L9.2 12L0 19.5Z" fill="#000"/><path d="M14 12H36" stroke="#007749" stroke-width="5"/><path d="M0 0L14 12L0 24" fill="none" stroke="#fff" stroke-width="1.2"/>',
    "ma": '<rect width="36" height="24" fill="#C1272D"/><path d="M18 6.2l1.6 4.9h5.1l-4.1 3 1.6 4.9-4.2-3-4.2 3 1.6-4.9-4.1-3h5.1z" fill="none" stroke="#006233" stroke-width="1"/>',
    "fr": '<rect width="12" height="24" fill="#002654"/><rect x="12" width="12" height="24" fill="#fff"/><rect x="24" width="12" height="24" fill="#CE1126"/>',
    "es": '<rect width="36" height="24" fill="#AA151B"/><rect y="6" width="36" height="12" fill="#F1BF00"/>',
    "ie": '<rect width="12" height="24" fill="#169B62"/><rect x="12" width="12" height="24" fill="#fff"/><rect x="24" width="12" height="24" fill="#FF883E"/>',
    "us": '<rect width="36" height="24" fill="#fff"/>' + "".join(f'<rect y="{i*24/6.5:.2f}" width="36" height="1.85" fill="#B22234"/>' for i in range(7)) + '<rect width="15" height="13" fill="#3C3B6E"/>',
    "ca": '<rect width="36" height="24" fill="#fff"/><rect width="9" height="24" fill="#D80621"/><rect x="27" width="9" height="24" fill="#D80621"/><path d="M18 5l1.6 3.2 2.4-.8-.8 4 2.6-.6-1 2.2 1.6 1.2-4.4 1.4.4 2.4H17.6l.4-2.4-4.4-1.4 1.6-1.2-1-2.2 2.6.6-.8-4 2.4.8z" fill="#D80621"/>',
    "de": '<rect width="36" height="8" fill="#000"/><rect y="8" width="36" height="8" fill="#DD0000"/><rect y="16" width="36" height="8" fill="#FFCE00"/>',
    "ae": '<rect width="36" height="8" fill="#00732F"/><rect y="8" width="36" height="8" fill="#fff"/><rect y="16" width="36" height="8" fill="#000"/><rect width="10" height="24" fill="#FF0000"/>',
    "in": '<rect width="36" height="8" fill="#FF9933"/><rect y="8" width="36" height="8" fill="#fff"/><rect y="16" width="36" height="8" fill="#138808"/><circle cx="18" cy="12" r="3" fill="none" stroke="#000080" stroke-width=".9"/>',
    "sg": '<rect width="36" height="12" fill="#EF3340"/><rect y="12" width="36" height="12" fill="#fff"/><circle cx="7" cy="6" r="4" fill="#fff"/><circle cx="8.6" cy="6" r="3.6" fill="#EF3340"/>',
    "au": '<rect width="36" height="24" fill="#012169"/><svg width="18" height="12" viewBox="0 0 36 24">' + UJ + '</svg>'
          '<circle cx="9" cy="18.5" r="2.2" fill="#fff"/><circle cx="27" cy="5" r="1.2" fill="#fff"/><circle cx="31" cy="10" r="1.2" fill="#fff"/><circle cx="23" cy="11" r="1.2" fill="#fff"/><circle cx="27" cy="19" r="1.3" fill="#fff"/>',
}


def flag(code):
    inner = FLAGS.get(code, '<rect width="36" height="24" fill="#ccc"/>')
    return f'<svg class="flag" viewBox="0 0 36 24" width="36" height="24" aria-hidden="true">{inner}</svg>'


CUR = ' aria-current="true"'


def region_list():
    rows = []
    for r in SITE.get("regions", []):
        langs = "".join(
            f'<a href="{"/" if l.get("lang", "en") == "en" else "/" + l["lang"] + "/"}" hreflang="{esc(l.get("lang", "en"))}" lang="{esc(l.get("lang", "en"))}" data-lang="{esc(l.get("lang", "en"))}"'
            + (' data-primary' if l.get("primary") else '') + (CUR if r.get("current") and l.get("primary") else '') + f'>{esc(l["label"])}</a>'
            for l in r["languages"])
        rows.append(f'<li class="region{" is-current" if r.get("current") else ""}">{flag(r["code"])}<span class="region-name">{esc(r["country"])}</span><span class="region-langs" translate="no">{langs}</span></li>')
    return '<ul class="region-list">' + "".join(rows) + "</ul>"


def current_region():
    for r in SITE.get("regions", []):
        if r.get("current"):
            return f'{r["country"]} · {r["languages"][0]["label"]}'
    return "Choose region"


def header():
    groups = {}
    for s in SERVICES:
        groups.setdefault(s["group"], []).append(s)
    svc_cols = "".join(f'<div class="mega-col"><p class="mega-label">{esc(g)}</p>' + "".join(f'<a href="/services/{s["slug"]}/">{esc(s["name"])}</a>' for s in items) + "</div>" for g, items in groups.items())
    thirds = [INDUSTRIES[0:3], INDUSTRIES[3:6], INDUSTRIES[6:9]]
    ind_cols = "".join(f'<div class="mega-col"><p class="mega-label">{lbl}</p>' + "".join(f'<a href="/industries/{i["slug"]}/">{esc(i["name"])}</a>' for i in col) + "</div>" for lbl, col in zip(("Industries", "&nbsp;", "&nbsp;"), thirds))
    about_cols = '''<div class="mega-col"><p class="mega-label">Who we are</p><a href="/about/">About us</a><a href="/about/#values">Our values</a><a href="/about/#approach">How we work</a></div>
<div class="mega-col"><p class="mega-label">Connect</p><a href="/contact/">Contact us</a><a href="/contact/#offices">Locations</a><a href="/careers/">Careers</a></div>'''
    return f'''<a class="skip" href="#main">Skip to main content</a>
<header class="site-header" id="top">
  <div class="mega-bg" aria-hidden="true"></div>
  <div class="header-inner">
    {logo()}
    <nav class="main-nav" aria-label="Main">
      <ul>
        <li class="has-mega"><button class="nav-link" aria-expanded="false">Services{CHEV}</button>
          <div class="mega"><div class="mega-inner">{svc_cols}<div class="mega-col"><p class="mega-label">&nbsp;</p><a class="mega-cta" href="/services/">All services →</a></div></div></div></li>
        <li class="has-mega"><button class="nav-link" aria-expanded="false">Industries{CHEV}</button>
          <div class="mega"><div class="mega-inner">{ind_cols}<div class="mega-col"><p class="mega-label">&nbsp;</p><a class="mega-cta" href="/industries/">All industries →</a></div></div></div></li>
        <li><a class="nav-link" href="/insights/">Insights</a></li>
        <li><a class="nav-link" href="/stories/">Stories</a></li>
        <li class="has-mega"><button class="nav-link" aria-expanded="false">Who we are{CHEV}</button>
          <div class="mega"><div class="mega-inner">{about_cols}</div></div></li>
        <li><a class="nav-link" href="/careers/">Careers</a></li>
      </ul>
      <details class="m-region"><summary>{flag(next((r["code"] for r in SITE.get("regions", []) if r.get("current")), "gb"))}<span>{esc(current_region())}</span>{CHEV}</summary>{region_list()}</details>
      <a class="btn btn-rev mobile-cta" href="/contact/">Let’s talk</a>
    </nav>
    <div class="header-actions">
      <a href="/contact/" class="btn header-cta">Let’s talk</a>
      <button class="icon-btn" id="searchToggle" aria-label="Search" aria-expanded="false">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      </button>
      <span class="divider" aria-hidden="true"></span>
      <div class="region-wrap">
        <button class="icon-btn region-btn" id="regionToggle" aria-label="Choose region and language" aria-expanded="false" aria-controls="regionPanel">
          <svg class="i-globe" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/></svg>
          <svg class="i-up" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.4"><path d="m6 15 6-6 6 6"/></svg>
        </button>
        <div class="region-panel" id="regionPanel" hidden>{region_list()}</div>
      </div>
      <button class="icon-btn burger" id="burger" aria-label="Open menu" aria-expanded="false"><span></span><span></span><span></span></button>
    </div>
  </div>
  <div class="search-panel" id="searchPanel" hidden>
    <form class="search-form" action="/search/" method="get" role="search">
      <label class="sr-only" for="hdrSearch">Search the site</label>
      <input id="hdrSearch" type="search" name="q" placeholder="Search services, stories and insights">
      <button class="btn btn-rev" type="submit">Search</button>
      <button class="search-close" type="button" id="searchClose" aria-label="Close search">×</button>
    </form>
  </div>
</header>
<div class="page-dim" id="pageDim" aria-hidden="true"></div>'''


def footer(prefooter=True):
    social = "".join(f'<a href="{esc(u)}" rel="noopener" target="_blank">{esc(n)}</a>' for n, u in SITE["social"].items())
    pre = f'''<section class="prefooter" aria-label="Get in touch"><div class="container">
  <h3 class="h3">Let’s build <em>together.</em></h3>
  {btn("Get in touch", "/contact/", "btn-lg btn-outline-rev")}
</div></section>''' if prefooter else ""
    return f'''{pre}
<footer class="site-footer">
  <div class="container footer-grid">
    <div class="footer-brand">{logo(light=True)}<p class="footer-tag">{esc(SITE["tagline"])}</p></div>
    <nav aria-label="Quick links"><p class="footer-h">Quick links</p>
      <a href="/services/ai-strategy/">AI strategy</a><a href="/services/customer-experience/">Customer experience</a><a href="/services/legacy-modernization/">Legacy modernization</a><a href="/insights/">Insights</a><a href="/stories/">Customer stories</a></nav>
    <nav aria-label="Company"><p class="footer-h">Company</p>
      <a href="/about/">Who we are</a><a href="/careers/">Careers</a><a href="/contact/">Contact</a><a href="/contact/#offices">Locations</a><a href="mailto:{esc(SITE["email"])}">{esc(SITE["email"])}</a></nav>
    <nav aria-label="Social"><p class="footer-h">Social</p>{social}<a href="/insights/feed.xml">RSS feed</a></nav>
  </div>
  <div class="footer-legal"><div class="container">
    <span class="tagline">Deeply human consulting</span>
    <span>©{datetime.now().year} {esc(SITE["name"])}. All rights reserved</span>
    <a href="/privacy/">Privacy notice</a><a href="/terms/">Terms of use</a><a href="/cookies/">Cookie notice</a><a href="/accessibility/">Accessibility</a>
  </div></div>
</footer>'''


FONTS = "https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400;1,500&family=Outfit:wght@300;400;500;600;700&display=swap"


def page(url, title, description, body, image=None, kind="Page", dark=False, accent=None, extra_head="", prefooter=True):
    full_title = f"{title} | {SITE['name']}" if title != SITE["name"] else SITE["name"]
    canonical = SITE["url"].rstrip("/") + url
    og_img = SITE["url"].rstrip("/") + (image or "/assets/images/hero-6.jpg")
    style = ""
    if accent:
        style = f' style="--page-accent:{accent[0]};--page-accent-text:{accent[1]}"'
    html_doc = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(full_title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:type" content="{'article' if kind in ('Insight', 'Story') else 'website'}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:image" content="{esc(og_img)}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="/assets/images/favicon.svg" type="image/svg+xml">
  <link rel="alternate" type="application/rss+xml" title="{esc(SITE['name'])} Insights" href="/insights/feed.xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{FONTS}" rel="stylesheet">
  <link rel="stylesheet" href="/styles.css">{extra_head}
</head>
<body class="{'on-dark dark-page' if dark else 'light-page'}"{style}>
{header()}
<main id="main">
{body}
</main>
{footer(prefooter)}
<script src="/main.js"></script>
</body>
</html>
'''
    out = ROOT / url.strip("/") / "index.html" if url.endswith("/") else ROOT / url.lstrip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc)
    PAGES.append({"url": url, "title": title, "type": kind, "summary": description, "text": plain(body)[:1500]})


# ---------------------------------------------------------------- components

def crumbs(*items):
    parts = ['<a href="/">Home</a>'] + [f'<a href="{u}">{esc(t)}</a>' if u else f'<span aria-current="page">{esc(t)}</span>' for t, u in items]
    return '<nav class="crumbs" aria-label="Breadcrumb">' + '<span aria-hidden="true">/</span>'.join(parts) + "</nav>"


def title_hero(h1_html, intro_strong="", intro="", crumb=(), tile_item=None, eyebrow=""):
    t = tile(tile_item, size="tile-lg") if tile_item else ""
    right = f'<div class="intro">{f"<strong>{intro_strong}</strong>" if intro_strong else ""}{f"<p>{intro}</p>" if intro else ""}</div>' if (intro or intro_strong) else "<div></div>"
    return f'''<section class="title-hero"><div class="container">
  {crumbs(*crumb) if crumb else ""}
  <div class="grid-2">
    <div>{f'<span class="eyebrow strong">{esc(eyebrow)}</span>' if eyebrow else ''}<div class="title-row">{t}<h1>{h1_html}</h1></div></div>
    {right}
  </div>
</div></section>'''


def image_hero(h1_html, lead, image, crumb=(), cta=""):
    return f'''<section class="image-hero"><img src="{image}" alt="" fetchpriority="high">
  <div class="container">{crumbs(*crumb) if crumb else ""}<h1>{h1_html}</h1>{f"<p>{lead}</p>" if lead else ""}{cta}</div>
</section>'''


def index_title(h1_html, intro, crumb=()):
    return f'''<section class="title-hero index-title"><div class="container">
  {crumbs(*crumb) if crumb else ""}
  <div class="grid-2"><h1 style="margin:0">{h1_html}</h1><p>{intro}</p></div>
</div></section>'''


def jumpbar(links, cta_href="/contact/"):
    return '<nav class="jumpbar" aria-label="On this page"><div class="container">' + "".join(f'<a href="#{i}">{esc(t)}</a>' for i, t in links) + \
        f'<a class="btn" href="{cta_href}">Let’s talk</a></div></nav>'


def card(href, image, tag, title, meta="", tags=""):
    return f'''<a class="card" href="{href}" data-item data-tags="{esc(tags)}">
  <div class="card-media"><img src="{image}" alt="" loading="lazy" onerror="this.remove()"></div>
  <div class="card-body"><span class="story-tag">{esc(tag)}</span><h3>{esc(title)}</h3>{f'<span class="story-meta">{esc(meta)}</span>' if meta else ''}</div>
</a>'''


def post_card(p):
    return card(f"/insights/{p['slug']}/", p["image"], f"Article · {p['category']}", p["title"], f"{nice_date(p['date'])} · {p['readtime']} min read", slugify(p["category"]))


def story_card(s):
    ind = IND.get(s["industry"], {}).get("name", "")
    return card(f"/stories/{s['slug']}/", s["image"], "Customer story", s["title"], s.get("client", ind), s["industry"])


def rail(heading_html, cards_html, dark=False, sid=""):
    if not cards_html:
        return ""
    return f'''<section class="band {'band-dark' if dark else 'light'} related"{f' id="{sid}"' if sid else ''}><div class="container" data-rail>
  <div class="rail-head"><h2>{heading_html}</h2><div class="rail-arrows"><button class="rail-arrow" data-rail-prev aria-label="Previous"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M19 12H5M11 6l-6 6 6 6"/></svg></button><button class="rail-arrow" data-rail-next aria-label="Next"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></div></div>
  <div class="rail-track">{cards_html}</div>
</div></section>'''


def feature_card(image, h3_html, button_html):
    return f'''<section class="feature-card"><img src="{image}" alt="" loading="lazy">
  <div class="container"><div class="fc-text"><h3>{h3_html}</h3>{button_html}</div></div></section>'''


def stats_band(claim_html, outcomes, note=""):
    st = "".join(f'<div class="stat"><span class="stat-value">{esc(o["value"])}</span><span class="stat-label">{esc(o["label"])}</span></div>' for o in outcomes)
    return f'''<section class="band band-navy"><div class="container">
  <div class="stats">{f'<h3 class="stats-claim">{claim_html}</h3>' if claim_html else ''}{st}</div>
  {f'<p class="fine" style="color:rgba(255,255,255,.7);margin-top:32px">{note}</p>' if note else ''}
</div></section>'''


def approach_block(dark=False, sid="approach"):
    steps = "".join(f'<li class="step"><span class="step-n" style="--t:{TILE_COLORS[(i * 2 + 4) % 8]}">{i + 1}</span><h3>{esc(a["title"])}</h3><p>{esc(a["text"])}</p></li>' for i, a in enumerate(SITE["approach"]))
    return f'<section class="band {"band-dark" if dark else ""}" id="{sid}"><div class="container"><h2>How we <em>work</em></h2><ol class="steps">{steps}</ol></div></section>'


def share(url, title, label="Share"):
    from urllib.parse import quote
    full = SITE["url"].rstrip("/") + url
    return f'''<div class="share-wrap"><button class="btn btn-sm btn-outline" type="button" data-share aria-expanded="false">{label}</button>
  <div class="share-menu" hidden>
    <a href="https://www.linkedin.com/sharing/share-offsite/?url={quote(full, safe='')}" target="_blank" rel="noopener">LinkedIn</a>
    <a href="https://twitter.com/intent/tweet?url={quote(full, safe='')}&amp;text={quote(title, safe='')}" target="_blank" rel="noopener">X (Twitter)</a>
    <a href="mailto:?subject={quote(title, safe='')}&amp;body={quote(full, safe='')}">Email</a>
    <button type="button" data-copy-link>Copy link</button>
  </div></div>'''


def chips(options, label):
    return f'<div class="chips" role="group" aria-label="{esc(label)}">' + "".join(
        f'<button class="chip{" is-active" if v == "all" else ""}" type="button" data-filter="{v}">{esc(t)}</button>' for v, t in options) + "</div>"


def list_tools(chip_opts, label, placeholder):
    return f'''<div class="list-tools">{chips(chip_opts, label)}
  <label class="list-search"><span class="sr-only">Search</span><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg><input type="search" data-search placeholder="{esc(placeholder)}"></label></div>
<p class="list-count" data-count aria-live="polite"></p>'''


def list_end():
    return '<p class="list-empty" data-empty hidden>Nothing matches yet — try another filter or search.</p><div class="show-more"><button class="btn btn-outline" type="button" data-more>Show more</button></div>'


def mailto_form(subject, note, fields_html, button="Send message", to=None):
    to = to or SITE["email"]
    return f'''<form class="form" data-form data-mailto="{esc(to)}" data-subject="{esc(subject)}" novalidate>
  {fields_html}
  <label class="check full"><input type="checkbox" name="consent" required> <span>I agree to {esc(SITE["name"])} using these details to respond to me, as described in the <a href="/privacy/">privacy notice</a>.</span></label>
  <div class="full form-actions"><button class="btn" type="submit">{button}</button><span class="form-note">{note}</span></div>
  <p class="form-msg full" aria-live="polite"></p>
</form>'''


# ---------------------------------------------------------------- pages

def related_cards(stories=(), posts=()):
    return "".join(story_card(STORY[x]) for x in stories if x in STORY) + "".join(post_card(POST[x]) for x in posts if x in POST)


def build_services():
    items = "".join(f'''<a class="svc-item" href="/services/{s["slug"]}/">{tile(s)}<div><h3>{esc(s["name"])}</h3><p>{esc(s["summary"])}</p></div></a>''' for s in SERVICES)
    body = image_hero("Services that turn ambition into <em>results</em>", "From strategy to delivery, we work side by side with your teams to design, build and scale what matters most.",
                      "/assets/images/feature-ai.jpg", crumb=(("Services", None),))
    body += f'''<section class="band"><div class="container">
  <div class="grid-2 svc-intro"><h2>Our <em>services</em></h2><p class="lead">Every engagement brings together the right mix of strategy, technology and delivery — so ideas become working results your teams can own.</p></div>
  <div class="svc-tiles">{items}</div>
</div></section>
<section class="band band-dark wave"><div class="container"><p class="statement center" style="max-width:1100px;margin:0 auto">We listen deeply, share what we know at every step, and leave your teams ready to <em class="hl">keep the momentum going</em> after we’re gone.</p></div></section>'''
    s0 = STORIES[0]
    body += feature_card(s0["image"], f'<strong>{esc(s0["client"])}:</strong> <em>{esc(s0["title"])}</em>', btn("Read story", f"/stories/{s0['slug']}/"))
    body += approach_block()
    body += rail("Stories &amp; <em>insights</em>", "".join(story_card(s) for s in STORIES[:4]) + "".join(post_card(p) for p in POSTS[:4]))
    page("/services/", "Services", "Strategy, technology and delivery services from Aethelon Global — AI, customer experience, data, cloud, modernization and more.", body, "/assets/images/feature-ai.jpg")

    for s in SERVICES:
        caps = "".join(f'<div class="cap"><h3>{esc(o["title"])}</h3><p>{esc(o["text"])}</p></div>' for o in s["offerings"])
        faq = "".join(f'<details class="faq-item"><summary>{esc(f["q"])}</summary><p>{esc(f["a"])}</p></details>' for f in s["faq"])
        rel = related_cards(s.get("related_stories", []), s.get("related_posts", []))
        if len(rel) == 0:
            rel = "".join(post_card(p) for p in POSTS[:3])
        st = STORY.get((s.get("related_stories") or [None])[0])
        body = title_hero(esc(s["name"]), esc(s["summary"]), esc(s["intro"]), crumb=(("Services", "/services/"), (s["name"], None)), tile_item=s)
        body += jumpbar([("expertise", "Expertise"), ("experience", "Our experience"), ("stories", "Stories and insights"), ("faq", "FAQ")], f"/contact/?topic={s['slug']}")
        if st:
            body += feature_card(st["image"], f'<strong>{esc(st["client"])}:</strong> <em>{esc(st["title"])}</em>', btn("Read story", f"/stories/{st['slug']}/"))
        else:
            body += feature_card(s["image"], f'<strong>{esc(s["name"])}:</strong> <em>{esc(s["tagline"])}</em>', btn("Talk to an expert", f"/contact/?topic={s['slug']}"))
        body += f'''<section class="band band-accent-tint" id="expertise"><div class="container">
  <h2>Our {esc(s["name"].lower())} <em>expertise</em></h2>
  <div class="cap-grid" style="--cols:4">{caps}</div>
</div></section>'''
        body += stats_band(f'What <em>{esc(s["name"].lower())}</em> can deliver', s["outcomes"], "Illustrative ranges from comparable engagements; results vary by organization.")
        body += approach_block(sid="experience")
        body += rail("Stories &amp; <em>insights</em>", rel, sid="stories")
        body += f'<section class="band band-soft" id="faq"><div class="container"><h2>Questions, <em>answered</em></h2><div class="faq-list">{faq}</div></div></section>'
        page(f"/services/{s['slug']}/", s["name"], s["summary"], body, s["image"], "Service", accent=(s["color"], s["text_color"]))


def build_industries():
    items = "".join(f'''<a class="svc-item" href="/industries/{x["slug"]}/">{tile(x)}<div><h3>{esc(x["name"])}</h3><p>{esc(x["summary"])}</p></div></a>''' for x in INDUSTRIES)
    body = image_hero("Deep industry knowledge, <em>practical</em> results", "Every sector has its own pressures, regulations and opportunities. We bring people who know yours.",
                      "/assets/images/story-6.jpg", crumb=(("Industries", None),))
    body += f'<section class="band"><div class="container"><div class="grid-2 svc-intro"><h2>Industries we <em>serve</em></h2><p class="lead">Specialists who understand your market, working with our service teams to deliver outcomes that matter in your world.</p></div><div class="svc-tiles">{items}</div></div></section>'
    body += rail("Stories &amp; <em>insights</em>", "".join(story_card(s) for s in STORIES))
    page("/industries/", "Industries", "Industry expertise from Aethelon Global across financial services, healthcare, public sector, retail, media, energy, manufacturing, sports and travel.", body, "/assets/images/story-6.jpg")

    for x in INDUSTRIES:
        ch = "".join(f'<div class="cap"><h3>{esc(c["title"])}</h3><p>{esc(c["text"])}</p></div>' for c in x["challenges"])
        hp = "".join(f'<div class="cap"><h3>{esc(h["title"])}</h3><p>{esc(h["text"])}</p><p style="margin-top:16px">{btn(SVC.get(h["service"], {}).get("name", "Learn more"), "/services/" + h["service"] + "/", "btn-sm btn-outline-rev")}</p></div>' for h in x["help"])
        rel = related_cards(x.get("related_stories", []), x.get("related_posts", [])) or "".join(post_card(p) for p in POSTS[:3])
        st = STORY.get((x.get("related_stories") or [None])[0])
        body = title_hero(esc(x["name"]), esc(x["summary"]), esc(x["intro"]), crumb=(("Industries", "/industries/"), (x["name"], None)), tile_item=x)
        body += jumpbar([("trends", "Challenges"), ("help", "How we help"), ("stories", "Stories and insights")], "/contact/")
        if st:
            body += feature_card(st["image"], f'<strong>{esc(st["client"])}:</strong> <em>{esc(st["title"])}</em>', btn("Read story", f"/stories/{st['slug']}/"))
        else:
            body += feature_card(x["image"], f'<strong>{esc(x["name"])}:</strong> <em>{esc(x["tagline"])}</em>', btn("Talk to us", "/contact/"))
        body += f'<section class="band band-accent-tint" id="trends"><div class="container"><h2>The challenges we <em>hear</em></h2><div class="cap-grid">{ch}</div></div></section>'
        body += f'<section class="band band-navy" id="help"><div class="container"><h2>How we <em>help</em></h2><div class="cap-grid">{hp}</div></div></section>'
        body += rail("Stories &amp; <em>insights</em>", rel, sid="stories")
        page(f"/industries/{x['slug']}/", x["name"], x["summary"], body, x["image"], "Industry", accent=(x["color"], x["text_color"]))


def build_insights():
    cats = sorted({p["category"] for p in POSTS})
    f = POSTS[0]
    feat = f'''<a class="featured" href="/insights/{f["slug"]}/">
  <div class="featured-media"><img src="{f["image"]}" alt="" loading="lazy"></div>
  <div class="featured-body"><span class="eyebrow" style="margin:0">Latest · {esc(f["category"])}</span><h2>{esc(f["title"])}</h2><p style="margin:0">{esc(f["excerpt"])}</p><span class="serif-meta">{nice_date(f["date"])}</span></div></a>'''
    body = index_title("Insights", "Practical thinking on AI, data, customer experience and modernization — from the people doing the work.", crumb=(("Insights", None),))
    body += f'<section class="band" style="padding-top:0"><div class="container">{feat}</div></section>'
    body += f'''<section class="band band-soft" data-list data-page-size="12"><div class="container">
  <h2>All <em>insights</em></h2>
  {list_tools([("all", "All topics")] + [(slugify(c), c) for c in cats], "Filter insights by topic", "Search insights")}
  <div class="card-grid">{"".join(post_card(p) for p in POSTS)}</div>
  {list_end()}
</div></section>'''
    page("/insights/", "Insights", "Articles and research from Aethelon Global on AI, data, customer experience, strategy and modernization.", body, f["image"])

    for p in POSTS:
        url = f"/insights/{p['slug']}/"
        same = [q for q in POSTS if q["slug"] != p["slug"] and q["category"] == p["category"]]
        others = same + [q for q in POSTS if q["slug"] != p["slug"] and q not in same]
        ld = json.dumps({"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"], "datePublished": p["date"],
                         "author": {"@type": "Organization", "name": SITE["name"]}, "publisher": {"@type": "Organization", "name": SITE["name"]},
                         "image": SITE["url"].rstrip("/") + p["image"], "description": p["excerpt"], "mainEntityOfPage": SITE["url"].rstrip("/") + url})
        body = f'''<section class="article-head"><div class="article-col">
  {crumbs(("Insights", "/insights/"), (p["category"], f"/insights/?filter={slugify(p['category'])}"))}
  <span class="eyebrow">Article</span>
  <h1>{esc(p["title"])}</h1>
  <p class="byline">By {esc(p["author"])}</p>
  <span class="article-date">{nice_date(p["date"])} · {p["readtime"]} min read</span>
  {share(url, p["title"], "Share insight")}
</div></section>
<div class="article-col article-lead-img"><img src="{p["image"]}" alt=""></div>
<article class="article-col prose"><p class="lead"><strong>{esc(p["excerpt"])}</strong></p>{p["html"]}</article>
<div class="article-col article-foot">{share(url, p["title"], "Share insight")}<hr class="rule-multi"></div>'''
        body += rail("Related <em>insights</em>", "".join(post_card(q) for q in others[:6]))
        page(url, p["title"], p["excerpt"], body, p["image"], "Insight", extra_head=f'\n  <script type="application/ld+json">{ld}</script>')


def build_stories():
    opts = [("all", "All industries")] + sorted({(s["industry"], IND.get(s["industry"], {}).get("name", s["industry"])) for s in STORIES}, key=lambda x: x[1])
    body = index_title("Customer <em>stories</em>", "How organizations like yours are using strategy, data and technology to make real change.", crumb=(("Stories", None),))
    body += f'''<section class="band" style="padding-top:0" data-list data-page-size="12"><div class="container">
  {list_tools(opts, "Filter stories by industry", "Search stories")}
  <div class="card-grid">{"".join(story_card(s) for s in STORIES)}</div>
  {list_end()}
</div></section>'''
    page("/stories/", "Customer stories", "Customer stories from Aethelon Global — how organizations achieve measurable outcomes with strategy, data and technology.", body, "/assets/images/story-7.jpg")

    for s in STORIES:
        url = f"/stories/{s['slug']}/"
        metrics = []
        for part in s.get("metrics", "").split("|"):
            if "=" in part:
                v, l = part.split("=", 1)
                metrics.append(f"<div><strong>{esc(v.strip())}</strong><span>{esc(l.strip())}</span></div>")
        svcs = [SVC[x.strip()] for x in s.get("services", "").split(",") if x.strip() in SVC]
        ind = IND.get(s["industry"])
        body = f'''<section class="story-intro"><div class="container">
  {crumbs(("Stories", "/stories/"), (ind["name"] if ind else "Story", None))}
  <div class="split">
    <div><p class="client">{esc(s.get("client", ""))}</p><h1>{esc(s["title"])}</h1>{share(url, s["title"], "Share story")}</div>
    <div class="split-media"><img src="{s["image"]}" alt=""></div>
  </div></div></section>
<section class="band band-dark wave" style="margin-top:var(--sep-xxl)"><div class="container glance">
  <div><h2>At a <em>glance</em></h2><p class="lead">{esc(s["excerpt"])}</p></div>
  <dl>
    <div><dt>Impact</dt><dd class="impact">{"".join(metrics)}</dd></div>
    {f'<div><dt>Industry</dt><dd><a href="/industries/{ind["slug"]}/">{esc(ind["name"])}</a></dd></div>' if ind else ''}
    <div><dt>Services</dt><dd>{", ".join(f'<a href="/services/{v["slug"]}/">{esc(v["name"])}</a>' for v in svcs)}</dd></div>
  </dl>
</div></section>
<article class="article-col prose band">{s["html"]}</article>'''
        if s.get("quote"):
            body += f'<section class="band band-soft"><div class="container"><blockquote class="xl-quote"><p>“{esc(s["quote"])}”</p><cite>{esc(s.get("quote_by", ""))}, {esc(s.get("client", ""))}</cite></blockquote></div></section>'
        body += f'<div class="article-col article-foot">{share(url, s["title"], "Share story")}<hr class="rule-multi"></div>'
        body += rail("More <em>stories</em>", "".join(story_card(x) for x in STORIES if x["slug"] != s["slug"]) + "".join(post_card(p) for p in POSTS[:2]))
        page(url, s["title"], s["excerpt"], body, s["image"], "Story")


def build_about():
    values = "".join(f'<div class="icon-item">{tile({"abbr": "".join(w[0] for w in v["title"].split()[:2]).title(), "color": TILE_COLORS[i * 2 % 8], "text_color": "#06192b" if TILE_COLORS[i * 2 % 8] in DARK_TEXT_ON else "#fff", "name": v["title"]})}<h3>{esc(v["title"])}</h3><p>{esc(v["text"])}</p></div>' for i, v in enumerate(SITE["values"]))
    body = image_hero("A <em>deeply human</em> consultancy", esc(SITE["description"]), "/assets/images/hero-3.jpg", crumb=(("Who we are", None),))
    body += f'''<section class="band band-dark wave"><div class="container">
  <p class="statement center" style="max-width:1100px;margin:0 auto var(--sep-xxl)">We help people and organizations <em class="hl">dream bigger, move faster,</em> and build better tomorrows for all.</p>
  <div id="values"><h2>What we <em>value</em></h2><div class="icon-grid" style="--cols:4">{values}</div></div>
</div></section>
<section class="band band-dark" style="padding-top:0"><div class="container">
  <div class="bleed">
    <figure class="bleed-media" style="margin:0"><img src="/assets/images/story-11.jpg" alt="" loading="lazy"></figure>
    <div class="bleed-text"><h2>Side by side, <em>start to finish</em></h2><p>We’re strategists, designers, engineers and data specialists who believe the best results come from working together. We don’t hand over a report and leave — we build with your teams until the change sticks.</p>{btn("Explore our services", "/services/", "btn-outline-rev")}</div>
  </div>
  <div class="bleed flip">
    <figure class="bleed-media" style="margin:0"><img src="/assets/images/story-3.jpg" alt="" loading="lazy"></figure>
    <div class="bleed-text"><h2>Life at <em>{esc(SITE["name"])}</em></h2><p>We hire curious, generous people and give them room to grow — with real responsibility, great colleagues and time to learn.</p>{btn("See open roles", "/careers/#roles", "btn-outline-rev")}</div>
  </div>
</div></section>'''
    body += approach_block()
    page("/about/", "Who we are", SITE["description"], body, "/assets/images/hero-3.jpg", dark=False)


def build_careers():
    teams = sorted({r["team"] for r in CAREERS})
    roles = "".join(f'''<a class="role" href="/careers/{r["slug"]}/" data-item data-tags="{slugify(r["team"])}">
  <div><h3>{esc(r["title"])}</h3><p>{esc(r["summary"])}</p></div>
  <div class="role-meta"><span>{esc(r["team"])}</span><span>{esc(r["location"])}</span><span>{esc(r["type"])}</span></div></a>''' for r in CAREERS)
    benefits = "".join(f'<div class="icon-item">{tile({"abbr": "".join(w[0] for w in b["title"].replace("&", "").split()[:2]).title(), "color": TILE_COLORS[(i + 1) % 8], "text_color": "#06192b" if TILE_COLORS[(i + 1) % 8] in DARK_TEXT_ON else "#fff", "name": b["title"]})}<h3>{esc(b["title"])}</h3><p>{esc(b["text"])}</p></div>' for i, b in enumerate(SITE["benefits"]))
    body = image_hero("Build your <em>career</em> with us", "Work on problems that matter, with people who care, and grow faster than you thought possible.", "/assets/images/story-10.jpg",
                      crumb=(("Careers", None),), cta=btn("See open roles", "#roles", "btn-rev"))
    body += f'<section class="band"><div class="container"><h2>Why join <em>us</em></h2><div class="icon-grid" style="--cols:3">{benefits}</div></div></section>'
    body += f'''<section class="band band-soft" id="roles" data-list data-page-size="20"><div class="container">
  <h2>Open <em>roles</em></h2>
  {list_tools([("all", "All teams")] + [(slugify(t), t) for t in teams], "Filter roles by team", "Search roles")}
  <div class="roles">{roles}</div>
  {list_end()}
  <p class="fine" style="margin-top:32px">Don’t see the right role? Send your CV to <a href="mailto:{esc(SITE["careers_email"])}">{esc(SITE["careers_email"])}</a>.</p>
</div></section>'''
    page("/careers/", "Careers", f"Careers at {SITE['name']} — open roles in AI, data, design, delivery, strategy and cloud.", body, "/assets/images/story-10.jpg")

    for r in CAREERS:
        fields = f'''<label>Full name<input name="name" autocomplete="name" required></label>
  <label>Email<input name="email" type="email" autocomplete="email" required></label>
  <label>Phone (optional)<input name="phone" type="tel" autocomplete="tel"></label>
  <label>LinkedIn or portfolio URL<input name="profile" type="url" placeholder="https://"></label>
  <label class="full">Why this role?<textarea name="message" rows="5" required></textarea></label>
  <input type="hidden" name="role" value="{esc(r["title"])}">'''
        body = title_hero(esc(r["title"]), esc(r["summary"]), f'{esc(r["team"])} · {esc(r["location"])} · {esc(r["type"])}', crumb=(("Careers", "/careers/"), (r["title"], None)))
        body += f'''<article class="article-col prose" style="padding-bottom:var(--sep-xxl)">
  <h2>About the role</h2><p>{esc(r["about"])}</p>
  <h2>What you’ll do</h2><ul>{"".join(f"<li>{esc(x)}</li>" for x in r["responsibilities"])}</ul>
  <h2>What you’ll bring</h2><ul>{"".join(f"<li>{esc(x)}</li>" for x in r["requirements"])}</ul>
  <h2>What we offer</h2><ul>{"".join(f"<li><strong>{esc(b['title'])}.</strong> {esc(b['text'])}</li>" for b in SITE["benefits"])}</ul>
  <p>We welcome applicants of every background and are happy to discuss adjustments to the process — just let us know.</p>
  <p>{btn("Apply now", "#apply")}</p>
</article>
<section class="band band-soft" id="apply"><div class="container form-wrap"><div><h2>Apply for this <em>role</em></h2>
<p>Fill in the form and your email app will open with your application ready to send — attach your CV before sending.</p></div>
{mailto_form(f"Application: {r['title']}", "Remember to attach your CV.", fields, "Prepare application", SITE["careers_email"])}</div></section>'''
        page(f"/careers/{r['slug']}/", r["title"], r["summary"], body, "/assets/images/story-10.jpg", "Career")


def build_contact():
    topic_opts = [("general", "General enquiry")] + [(s["slug"], s["name"]) for s in SERVICES] + [("newsletter", "Insights mailing list"), ("press", "Press & media"), ("partnership", "Partnerships")]
    options = "".join(f'<option value="{esc(v)}">{esc(t)}</option>' for v, t in topic_opts)
    fields = f'''<label>Full name<input name="name" autocomplete="name" required></label>
  <label>Work email<input name="email" type="email" autocomplete="email" required></label>
  <label>Company<input name="company" autocomplete="organization"></label>
  <label>Topic<select name="topic" id="topicSelect">{options}</select></label>
  <label class="full">How can we help?<textarea name="message" rows="5" required></textarea></label>'''
    def office(i, o):
        from urllib.parse import quote_plus
        lines = o.get("lines") or [o.get("detail", "")]
        addr = "<br>".join(esc(l) for l in lines)
        maps = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(", ".join(lines))
        head = f'<div class="office-head">{flag(o["code"])}<h3>{esc(o.get("country", o.get("city", "")))}</h3></div>' if o.get("code") else f'<h3>{esc(o.get("city", ""))}</h3>'
        hours = f'<p class="fine">{esc(o["hours"])}</p>' if o.get("hours") else ""
        return (f'<div class="icon-item office">'
                f'{head}<p class="office-city">{esc(o.get("city", ""))}</p><address translate="no">{addr}</address>{hours}'
                f'<p><a class="office-map" href="{esc(maps)}" target="_blank" rel="noopener">View on map</a></p></div>')
    offices = "".join(office(i, o) for i, o in enumerate(SITE["offices"]))
    phone = f'<p><a href="tel:{esc(SITE["phone"])}">{esc(SITE["phone"])}</a></p>' if SITE.get("phone") else ""
    body = index_title("Let’s <em>talk</em>", "Tell us about your goals and we’ll connect you with the right people — usually within one business day.", crumb=(("Contact", None),))
    body += f'''<section class="band" style="padding-top:0"><div class="container form-wrap">
  <div><h2>Send us a <em>message</em></h2><p>Prefer email? Write to <a href="mailto:{esc(SITE["email"])}">{esc(SITE["email"])}</a>.</p>{phone}
    <p><strong>Careers</strong><br><a href="mailto:{esc(SITE["careers_email"])}">{esc(SITE["careers_email"])}</a></p>
    <p><strong>Press</strong><br><a href="mailto:{esc(SITE["press_email"])}">{esc(SITE["press_email"])}</a></p></div>
  {mailto_form("Website enquiry", "We reply within one business day.", fields)}
</div></section>
<section class="band band-soft" id="offices"><div class="container"><h2>Where to <em>find us</em></h2><div class="icon-grid" style="--cols:3">{offices}</div></div></section>
<script>(function(){{var t=new URLSearchParams(location.search).get('topic'),s=document.getElementById('topicSelect');if(t&&s&&[].some.call(s.options,function(o){{return o.value===t}}))s.value=t;}})();</script>'''
    page("/contact/", "Contact", f"Contact {SITE['name']} — talk to our team about AI, data, customer experience and technology.", body, prefooter=False)

LEGAL = {
    "privacy": ("Privacy notice", [
        ("Who we are", f"{SITE['name']} (“we”, “us”) is responsible for the personal information collected through this website. Contact us at {SITE['email']} with any privacy question."),
        ("What we collect", "When you contact us or apply for a role, we receive the details you choose to send — such as your name, email address, company and message. Our website forms open your own email app; we receive only what you send. We do not use advertising cookies."),
        ("How we use it", "We use your information to respond to you, to consider job applications, and — if you ask — to send you our insights. We do not sell your personal information."),
        ("How long we keep it", "We keep enquiries for as long as needed to respond and maintain our relationship, and job applications for up to 12 months unless you ask us to delete them sooner."),
        ("Your rights", f"Depending on where you live, you may have the right to access, correct, delete or restrict use of your information, and to complain to a data-protection authority. Email {SITE['email']} to make a request."),
        ("Changes", "We may update this notice from time to time. The date at the bottom of this page shows when it was last updated."),
    ]),
    "cookies": ("Cookie notice", [
        ("Our approach", "This website is built to work without tracking cookies. We do not use advertising or cross-site tracking cookies."),
        ("What may be stored", "Your browser may store essential files (such as cached images and fonts) so pages load quickly. Fonts are loaded from Google Fonts, which may receive your IP address as part of serving them."),
        ("Managing cookies", "You can clear or block cookies and site data at any time in your browser settings. Blocking them will not stop this site from working."),
        ("Changes", f"If we add analytics or other cookies in future, we will update this notice and ask for your consent where required. Questions: {SITE['email']}."),
    ]),
    "accessibility": ("Accessibility statement", [
        ("Our commitment", f"{SITE['name']} wants everyone to be able to use this website. We aim to meet the Web Content Accessibility Guidelines (WCAG) 2.2 at level AA."),
        ("What we’ve done", "Pages use semantic headings and landmarks, keyboard-accessible menus, visible focus, text alternatives, sufficient colour contrast, captions-ready video players and respect for reduced-motion settings."),
        ("Known limitations", "Some background videos are decorative and have no audio description. If any content is hard to use, please tell us."),
        ("Feedback", f"If you find a barrier or need information in a different format, email {SITE['email']}. We aim to respond within five business days."),
    ]),
    "terms": ("Terms of use", [
        ("Using this site", f"By using this website you agree to these terms. The site is provided by {SITE['name']} for general information about our services."),
        ("Content", "Articles and insights are general information, not professional advice for your specific situation. Examples and figures are illustrative."),
        ("Intellectual property", f"Unless stated otherwise, content on this site belongs to {SITE['name']}. You may share links and short quotations with attribution."),
        ("Links", "We link to other websites for convenience; we are not responsible for their content or practices."),
        ("Liability", "We work to keep the site accurate and available but cannot guarantee it is always error-free or uninterrupted."),
        ("Contact", f"Questions about these terms: {SITE['email']}."),
    ]),
}




def legal_from_file(slug):
    """content/legal/<slug>.md: 'key: value' lines, then ---, then markdown."""
    f = C / "legal" / f"{slug}.md"
    if not f.exists():
        return False
    head, _, text = f.read_text().partition("\n---\n")
    meta = dict(l.split(":", 1) for l in head.splitlines() if ":" in l)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    title = meta.get("title", slug.title())
    html_body = md(text)
    toc = "".join(f'<li><a href="#{a}">{h}</a></li>' for a, h in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html_body))
    body = (f'<section class="article-head"><div class="article-col">{crumbs((title, None))}<h1>{esc(title)}</h1>'
            f'<p class="serif-meta">Last updated {esc(meta.get("updated", ""))}</p></div></section>'
            f'<article class="article-col prose legal" style="padding:32px var(--gutter) var(--sep-xxl)">'
            f'<nav class="legal-toc" aria-label="On this page"><p class="eyebrow">On this page</p><ol>{toc}</ol></nav>{html_body}</article>')
    page(f"/{slug}/", title, meta.get("summary", f"{title} for the {SITE['name']} website."), body, kind="Legal")
    return True


def build_legal():
    today = datetime.now().strftime("%B %-d, %Y")
    for slug, (title, sections) in LEGAL.items():
        if legal_from_file(slug):
            continue
        prose = "".join(f"<h2>{esc(h)}</h2><p>{esc(t)}</p>" for h, t in sections) + f'<p class="fine">Last updated {today}. This is a starting template — have it reviewed by a legal professional before launch.</p>'
        body = f'<section class="article-head"><div class="article-col">{crumbs((title, None))}<h1>{esc(title)}</h1></div></section><article class="article-col prose" style="padding:48px var(--gutter) var(--sep-xxl)">{prose}</article>'
        page(f"/{slug}/", title, f"{title} for the {SITE['name']} website.", body, kind="Legal")


def build_search_and_404():
    body = index_title("Search", "Find services, industries, stories, insights and roles.", crumb=(("Search", None),))
    body += '''<section class="band" style="padding-top:0"><div class="container narrow">
  <form class="search-big" role="search" onsubmit="return false"><label class="sr-only" for="searchInput">Search the site</label>
  <input id="searchInput" type="search" placeholder="Search services, stories, insights and roles" autofocus></form>
  <p id="searchStatus" class="list-count" aria-live="polite" style="margin-top:20px"></p>
  <div id="searchResults" class="search-results"></div>
</div></section>'''
    page("/search/", "Search", f"Search the {SITE['name']} website.", body, kind="Search")
    PAGES.pop()
    body = index_title("Page not <em>found</em>", "The page you’re looking for has moved or doesn’t exist.")
    body += f'<section class="band" style="padding-top:0"><div class="container"><p>{btn("Go to the home page", "/")} {btn("Search the site", "/search/", "btn-outline")}</p></div></section>'
    page("/404.html", "Page not found", "This page could not be found.", body, kind="Error")
    PAGES.pop()


def refresh_home():
    p = ROOT / "index.html"
    t = p.read_text()
    feed = []
    for s in STORIES:
        feed.append({"type": "Customer story", "title": s["title"], "meta": s.get("client", ""), "href": f"/stories/{s['slug']}/", "image": s["image"], "date": s["date"]})
    for q in POSTS:
        feed.append({"type": "Article", "title": q["title"], "meta": nice_date(q["date"]), "href": f"/insights/{q['slug']}/", "image": q["image"], "date": q["date"]})
    feed.sort(key=lambda x: x["date"], reverse=True)
    blocks = {
        "HEADER": header(),
        "FOOTER": footer(),
        "FEED": f"<script>window.HOME_FEED = {json.dumps(feed)};</script>",
        "SVC_TILES": tiles_block(SERVICES, "services", 5),
        "IND_TILES": tiles_block(INDUSTRIES, "industries", 5),
    }
    for name, content in blocks.items():
        start, end = f"<!-- BUILD:{name} -->", f"<!-- /BUILD:{name} -->"
        if start not in t:
            raise SystemExit(f"index.html is missing the {start} marker")
        t = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: f"{start}\n{content}\n{end}", t, flags=re.S)
    t = re.sub(r'href="https://fonts\.googleapis\.com/css2\?[^"]+"', f'href="{FONTS.replace("&", "&amp;")}"', t)
    p.write_text(t)
    PAGES.insert(0, {"url": "/", "title": SITE["name"], "type": "Page", "summary": SITE["description"], "text": ""})


def build_feeds():
    base = SITE["url"].rstrip("/")
    now = datetime.now(timezone.utc)
    items = "".join(f'''<item><title>{esc(p["title"])}</title><link>{base}/insights/{p["slug"]}/</link><guid>{base}/insights/{p["slug"]}/</guid>
<pubDate>{datetime.strptime(p["date"], "%Y-%m-%d").strftime("%a, %d %b %Y 09:00:00 +0000")}</pubDate><category>{esc(p["category"])}</category><description>{esc(p["excerpt"])}</description></item>''' for p in POSTS)
    (ROOT / "insights" / "feed.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{esc(SITE["name"])} Insights</title><link>{base}/insights/</link><description>{esc(SITE["description"])}</description>
<lastBuildDate>{now.strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>{items}</channel></rss>
''')
    urls = "".join(f"<url><loc>{base}{p['url']}</loc></url>" for p in PAGES if p["url"] != "/404.html")
    (ROOT / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    (ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    (ROOT / "search-index.json").write_text(json.dumps([p for p in PAGES if p["type"] not in ("Error", "Search")], ensure_ascii=False))


def check_links():
    bad = set()
    for f in list(ROOT.glob("**/index.html")) + [ROOT / "404.html"]:
        if any(part.startswith(".") or part in ("content", "assets") for part in f.relative_to(ROOT).parts):
            continue
        text = f.read_text()
        ids = set(re.findall(r'id="([^"]+)"', text))
        for href in re.findall(r'href="(/[^"#?]*)', text):
            target = ROOT / href.lstrip("/")
            if href.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                bad.add((href, str(f.relative_to(ROOT))))
        for frag in re.findall(r'href="#([^"]+)"', text):
            if frag not in ids and frag not in ("main",):
                bad.add(("#" + frag, str(f.relative_to(ROOT))))
    return sorted(bad)


if __name__ == "__main__":
    build_services()
    build_industries()
    build_insights()
    build_stories()
    build_about()
    build_careers()
    build_contact()
    build_legal()
    build_search_and_404()
    refresh_home()
    build_feeds()
    import translate  # republish /de/ /fr/ /es/ /ar/ from translations/*.json (no API calls)
    translate.publish(offline=True, quiet=True)
    broken = check_links()
    print(f"Built {len(PAGES)} pages: {len(SERVICES)} services, {len(INDUSTRIES)} industries, {len(POSTS)} insights, {len(STORIES)} stories, {len(CAREERS)} roles.")
    if broken:
        print("Broken links:")
        for href, src in broken:
            print(f"  {href}  (in {src})")
    else:
        print("All internal links resolve.")
