#!/usr/bin/env python3
"""Publish the site in every language listed in content/site.json.

    python3 translate.py              translate new or changed English text with OpenRouter, then publish
    python3 translate.py --offline    publish from the saved translations only (no API calls)
    python3 translate.py --only de    work on one language
    python3 translate.py --model ...  use a different OpenRouter model

How it works
  * build.py writes the English site. This script reads every English page, splits it into
    text segments (headings, paragraphs, buttons, alt text, page titles...) and looks each one
    up in translations/<lang>.json.
  * Anything missing is sent to OpenRouter in batches; the results are saved back to that file.
  * Translated copies are written to /de/, /fr/, /es/, /ar/ with links, search, sitemap and
    hreflang tags pointing at the right language. Arabic pages are laid out right-to-left.

Editing translations
  Open translations/<lang>.json and change any value; your edit is kept on later runs.
  If you change the English text, that segment is translated again.
  Rebuilding with python3 build.py republishes all languages from these files automatically.
"""
import argparse
import concurrent.futures as cf
import getpass
import html
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = json.loads((ROOT / "content" / "site.json").read_text())
TDIR = ROOT / "translations"
DEFAULT_MODEL = "google/gemini-3.1-flash-lite"
LANGS = [l for l in SITE.get("languages", []) if not l.get("source")]
LANG_NAMES = {"de": "German", "fr": "French", "es": "Spanish", "ar": "Arabic", "hi": "Hindi"}
STYLE = {
    "de": "Use the formal 'Sie' form.",
    "fr": "Use the formal 'vous' form and French typography (e.g. a space before : ; ? !).",
    "es": "Use the formal 'usted' form and neutral international Spanish.",
    "ar": "Use Modern Standard Arabic suitable for a professional services firm in the Gulf region.",
    "hi": "Use clear, professional standard Hindi in Devanagari script, the 'आप' form, and keep widely used English business and technology terms (AI, cloud, data, platform) in English or in common Hindi transliteration where Indian business readers would expect it.",
}
SKIP_DIRS = {"content", "assets", "translations", "node_modules", ".claude", ".git"}
NOT_LINKED = ("/assets/", "/styles.css", "/main.js", "/insights/feed.xml", "/sitemap.xml", "/robots.txt", "/favicon")

# Strings the browser script shows (main.js looks these up in window.I18N)
JS_STRINGS = [
    "Close menu", "Open menu", "Go to slide {n}", "Play", "Pause", "This video is not available yet.",
    "{n} result", "{n} results", "Type to search pages, services, stories and insights.",
    "{n} result for “{q}”", "{n} results for “{q}”", "Search is unavailable right now.", "Link copied ✓",
    "Copy this link:", "Please complete the highlighted fields.", "Thank you — we’ll be in touch shortly.",
    "Website enquiry", "Your email app should open with your message ready to send. If it doesn’t, email us at {email}.",
]

INLINE = {"a", "abbr", "b", "br", "cite", "code", "em", "i", "mark", "q", "s", "small", "span", "strong", "sub", "sup", "time", "u", "wbr"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
OPAQUE = {"#comment", "script", "style", "svg", "code", "pre", "template", "textarea"}
ATTRS = ("alt", "title", "aria-label", "placeholder", "data-film-title", "data-success", "data-subject")
FONTS = {"ar": "IBM+Plex+Sans+Arabic:wght@300;400;500;600;700", "hi": "Noto+Sans+Devanagari:wght@300;400;500;600;700"}
FLIP = str.maketrans("→←", "←→")
META_KEYS = ("description", "og:title", "og:description", "twitter:title", "twitter:description")


# ---------------------------------------------------------------- HTML segmentation
class Node:
    __slots__ = ("tag", "attrs", "start", "inner", "inner_end", "end", "children", "parent")

    def __init__(self, tag, attrs, start, inner, parent):
        self.tag, self.attrs, self.start, self.inner, self.parent = tag, dict(attrs), start, inner, parent
        self.inner_end = self.end = None
        self.children = []


class Text:
    __slots__ = ("start", "end")

    def __init__(self, start, end):
        self.start, self.end = start, end


class Tree(HTMLParser):
    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.src = src
        self.lines = [0]
        for m in re.finditer("\n", src):
            self.lines.append(m.end())
        self.root = Node("#root", [], 0, 0, None)
        self.cur = self.root
        self.feed(src)
        self.close()
        while self.cur is not self.root:
            self._close(self.cur, len(src), len(src))
        self.root.inner_end = self.root.end = len(src)

    def _pos(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def _close(self, node, inner_end, end):
        node.inner_end, node.end = inner_end, end
        self.cur = node.parent

    def handle_starttag(self, tag, attrs):
        start = self._pos()
        raw = self.get_starttag_text() or ""
        node = Node(tag, attrs, start, start + len(raw), self.cur)
        self.cur.children.append(node)
        if tag in VOID:
            node.inner_end = node.end = node.inner
        else:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        start = self._pos()
        raw = self.get_starttag_text() or ""
        node = Node(tag, attrs, start, start + len(raw), self.cur)
        node.inner_end = node.end = node.inner
        self.cur.children.append(node)

    def handle_endtag(self, tag):
        start = self._pos()
        end = self.src.index(">", start) + 1
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is self.root:
            return  # stray end tag
        while self.cur is not n:
            self._close(self.cur, start, start)
        self._close(n, start, end)

    def _text(self, _data=None):
        start = self._pos()
        # the parser has already advanced; find the end as the next tag start
        nxt = self.src.find("<", start + 1) if self.cur.tag not in ("script", "style") else self.src.find("</" + self.cur.tag, start)
        end = nxt if nxt != -1 else len(self.src)
        last = self.cur.children[-1] if self.cur.children else None
        if isinstance(last, Text) and start <= last.end:
            last.end = max(last.end, end)
        else:
            self.cur.children.append(Text(start, end))

    handle_data = handle_entityref = handle_charref = _text

    def handle_comment(self, data):
        start = self._pos()
        node = Node("#comment", [], start, start, self.cur)
        node.inner_end = node.end = self.src.index("-->", start) + 3
        self.cur.children.append(node)


def _skipped(n):
    return n.tag in OPAQUE or n.attrs.get("translate") == "no"


def _inline_pure(n, memo):
    if id(n) in memo:
        return memo[id(n)]
    ok = n.tag in INLINE and not _skipped(n) and all(isinstance(c, Text) or _inline_pure(c, memo) for c in n.children)
    memo[id(n)] = ok
    return ok


HAS_WORD = re.compile(r"[^\W\d_]{2,}", re.U)


def text_only(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def segments(src):
    """Return [(start, end, raw_html)] for every translatable text run."""
    tree = Tree(src)
    memo, out = {}, []

    def flush(run):
        if not run:
            return
        a, b = run[0].start, run[-1].end
        raw = src[a:b]
        lead = len(raw) - len(raw.lstrip())
        trail = len(raw) - len(raw.rstrip())
        a, b = a + lead, b - trail
        if b > a and HAS_WORD.search(text_only(src[a:b])):
            out.append((a, b, src[a:b]))

    def walk(n):
        run = []
        for c in n.children:
            if isinstance(c, Text) or _inline_pure(c, memo):
                run.append(c)
                continue
            flush(run)
            run = []
            if not _skipped(c):
                walk(c)
        flush(run)

    walk(tree.root)
    # drop runs inside <head> except <title>
    head = re.search(r"<head\b.*?</head>", src, re.S)
    if head:
        title = re.search(r"<title>.*?</title>", src, re.S)
        out = [s for s in out if not (head.start() <= s[0] < head.end()) or (title and title.start() <= s[0] < title.end())]
    return out


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


TAG_RE = re.compile(r"<[a-zA-Z][^<>]*>")


def tag_attrs(tag_html):
    """Translatable attribute values inside one start tag."""
    vals = []
    for a in ATTRS:
        m = re.search(r'\s%s="([^"]*)"' % re.escape(a), tag_html)
        if m and HAS_WORD.search(html.unescape(m.group(1))):
            vals.append(m.group(1))
    if tag_html.startswith("<meta"):
        k = re.search(r'\s(?:name|property)="([^"]+)"', tag_html)
        c = re.search(r'\scontent="([^"]*)"', tag_html)
        if k and c and k.group(1) in META_KEYS:
            vals.append(c.group(1))
    return vals


def outside_scripts(src):
    """Yield (start, end) spans of the document outside <script> and <style> blocks."""
    pos = 0
    for m in re.finditer(r"<(script|style)\b.*?</\1>", src, re.S):
        yield pos, m.start()
        pos = m.end()
    yield pos, len(src)


def feed_items(src):
    m = re.search(r"window\.HOME_FEED = (\[.*?\]);</script>", src, re.S)
    return (m, json.loads(m.group(1))) if m else (None, [])


def collect(src):
    keys = [norm(raw) for _, _, raw in segments(src)]
    for a, b in outside_scripts(src):
        for t in TAG_RE.findall(src[a:b]):
            keys += [norm(v) for v in tag_attrs(t)]
    _, items = feed_items(src)
    for it in items:
        keys += [norm(html.escape(it[k], quote=False)) for k in ("type", "title", "meta") if it.get(k) and HAS_WORD.search(it[k])]
    return keys


# ---------------------------------------------------------------- translation memory
def load_tm(code):
    p = TDIR / f"{code}.json"
    if p.exists():
        return json.loads(p.read_text()).get("strings", {})
    return {}


def save_tm(code, tm, used):
    TDIR.mkdir(exist_ok=True)
    keep = {k: tm[k] for k in sorted(used) if k in tm}
    data = {
        "_about": f"{LANG_NAMES.get(code, code)} translations for the website. Keys are the English text (with any inline HTML); "
                  "values are what gets published. Edit any value and run python3 build.py to republish. "
                  "Keep HTML tags and {placeholders} exactly as they are.",
        "strings": keep,
    }
    (TDIR / f"{code}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def tags_of(s):
    return re.findall(r"</?([a-zA-Z0-9]+)", s)


def holes(s):
    return sorted(re.findall(r"\{[a-z]+\}", s))


def valid(src, out):
    return isinstance(out, str) and out.strip() and tags_of(src) == tags_of(out) and holes(src) == holes(out)


# ---------------------------------------------------------------- OpenRouter
def api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        key = getpass.getpass("OpenRouter API key (hidden): ").strip()
    return key


def call(key, model, code, batch):
    lang = LANG_NAMES.get(code, code)
    system = (
        f"You are a professional website translator. Translate each JSON value from English into {lang} for the website of "
        "Aethelon Global, a business, technology and AI consulting company. Rules: "
        "1) Keep every HTML tag and attribute exactly as given and in the same order; translate only the human-readable text. "
        "2) Keep HTML entities valid (e.g. &amp;). "
        "3) Never translate the brand names 'Aethelon Global' or 'Aethelon'. "
        "4) Keep placeholders such as {n}, {q} and {email} unchanged. "
        "5) Keep well-known product and technology names (AI, AWS, Azure, Salesforce, SAP, etc.) as they are normally written. "
        "6) Write natural, confident, professional marketing copy, not a word-for-word rendering; keep short labels short. "
        f"7) {STYLE.get(code, '')} "
        "Return only a JSON object with exactly the same keys."
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": json.dumps({str(i): s for i, s in enumerate(batch)}, ensure_ascii=False)}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "usage": {"include": True},
    }).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json",
        "HTTP-Referer": SITE.get("url", "https://example.com"), "X-Title": "Website translation"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (401, 402, 403):
                raise SystemExit(f"OpenRouter refused the request ({e.code}): {msg}")
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    text = data["choices"][0]["message"]["content"] or "{}"
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        out = {}
    cost = float((data.get("usage") or {}).get("cost") or 0)
    return {batch[int(k)]: v for k, v in out.items() if k.isdigit() and int(k) < len(batch)}, cost


def batches(items, max_items=50, max_chars=7000):
    cur, size = [], 0
    for s in items:
        if cur and (len(cur) >= max_items or size + len(s) > max_chars):
            yield cur
            cur, size = [], 0
        cur.append(s)
        size += len(s)
    if cur:
        yield cur


def translate_missing(code, tm, needed, key, model):
    missing = [s for s in needed if s not in tm]
    if not missing:
        print(f"  {code}: everything already translated")
        return 0.0, []
    print(f"  {code}: translating {len(missing)} new segments with {model} ...")
    total, failed = 0.0, []
    work = list(batches(missing))
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for got, cost in pool.map(lambda b: call(key, model, code, b), work):
            total += cost
            for src, out in got.items():
                if valid(src, out):
                    tm[src] = out
    retry = [s for s in missing if s not in tm]
    if retry:  # one more pass, smaller batches
        with cf.ThreadPoolExecutor(max_workers=6) as pool:
            for got, cost in pool.map(lambda b: call(key, model, code, b), list(batches(retry, 8, 2000))):
                total += cost
                for src, out in got.items():
                    if valid(src, out):
                        tm[src] = out
        failed = [s for s in missing if s not in tm]
    return total, failed


# ---------------------------------------------------------------- publishing
def english_pages():
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT)
        if rel.parts[0] in SKIP_DIRS or rel.parts[0] in {l["code"] for l in LANGS} or rel.parts[0].startswith("."):
            continue
        yield rel, p.read_text()


def url_of(rel):
    s = "/" + str(rel).replace(os.sep, "/")
    return s[: -len("index.html")] if s.endswith("index.html") else s


def localize(src, rel, lang, tm):
    code, base = lang["code"], "/" + lang["code"]
    tr = lambda raw: tm.get(norm(raw))

    # 1) text segments
    out, pos = [], 0
    for a, b, raw in segments(src):
        t = tr(raw)
        out.append(src[pos:a])
        if t is not None and lang.get("dir") == "rtl":
            t = t.translate(FLIP)  # arrows point the reading direction
        out.append(t if t is not None else raw)
        pos = b
    out.append(src[pos:])
    doc = "".join(out)

    # 2) attributes and links (outside scripts)
    def fix_tag(m):
        t = m.group(0)
        for v in tag_attrs(t):
            new = tr(v)
            if new is not None:
                t = t.replace(f'="{v}"', '="' + new.replace('"', "&quot;") + '"', 1)
        if "data-lang" in t:
            return t

        def link(mm):
            attr, val = mm.group(1), mm.group(2)
            if val.startswith(("http:", "https:", "mailto:", "tel:", "data:", "javascript:", "#", "//")):
                return mm.group(0)
            if not val.startswith("/"):
                if attr == "href" and not re.search(r"\.(css|js|svg|png|jpe?g|webp|mp4|xml|json|ico)$", val):
                    return mm.group(0)
                return f'{attr}="/{val}"'  # root-relative assets on the home page
            if val.startswith(NOT_LINKED):
                return mm.group(0)
            if attr in ("href", "action"):
                return f'{attr}="{base}{val}"'
            return mm.group(0)

        return re.sub(r'\b(href|action|src|poster|data-src|data-film)="([^"]*)"', link, t)

    parts, pos = [], 0
    for a, b in outside_scripts(doc):
        parts.append(doc[pos:a])
        parts.append(TAG_RE.sub(fix_tag, doc[a:b]))
        pos = b
    doc = "".join(parts)

    # 3) home feed data
    m, items = feed_items(doc)
    if m:
        for it in items:
            for k in ("type", "title", "meta"):
                if it.get(k):
                    t = tr(html.escape(it[k], quote=False))
                    if t is not None:
                        it[k] = html.unescape(t)
            it["href"] = base + it["href"]
        doc = doc[: m.start(1)] + json.dumps(items, ensure_ascii=False).replace("</", "<\\/") + doc[m.end(1):]

    # 4) document language, direction, canonical, script strings
    attrs = f' lang="{code}" data-base="{base}"' + (' dir="rtl"' if lang.get("dir") == "rtl" else "")
    doc = re.sub(r"<html\b[^>]*>", f"<html{attrs}>", doc, count=1)
    site = SITE["url"].rstrip("/")
    doc = re.sub(r'(<link rel="canonical" href="|<meta property="og:url" content=")' + re.escape(site) + r"/", r"\g<1>" + site + base + "/", doc)
    strings = {s: tm[s] for s in JS_STRINGS if s in tm}
    extra = f'<script>window.I18N = {json.dumps(strings, ensure_ascii=False)};</script>'
    font = FONTS.get(code)
    if font:
        extra += f'\n  <link href="https://fonts.googleapis.com/css2?family={font}&amp;display=swap" rel="stylesheet">'
    doc = doc.replace("</head>", f"  {extra}\n</head>", 1)
    return doc


def alternates(url):
    site = SITE["url"].rstrip("/")
    links = [f'<link rel="alternate" hreflang="en" href="{site}{url}">']
    links += [f'<link rel="alternate" hreflang="{l["code"]}" href="{site}/{l["code"]}{url}">' for l in LANGS]
    links.append(f'<link rel="alternate" hreflang="x-default" href="{site}{url}">')
    return "<!-- i18n -->" + "".join(links) + "<!-- /i18n -->"


def add_alternates(doc, url):
    doc = re.sub(r"\s*<!-- i18n -->.*?<!-- /i18n -->", "", doc, flags=re.S)
    return doc.replace("</head>", f"  {alternates(url)}\n</head>", 1)


def search_index(lang, tm, pages_html):
    base = "/" + lang["code"]
    src = json.loads((ROOT / "search-index.json").read_text())
    out = []
    for p in src:
        q = dict(p)
        for k in ("title", "summary", "type"):
            t = tm.get(norm(html.escape(p.get(k, ""), quote=False)))
            if t:
                q[k] = html.unescape(re.sub(r"<[^>]+>", "", t))
        doc = pages_html.get(p["url"])
        if doc:
            main = re.search(r"<main\b.*?</main>", doc, re.S)
            text = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", main.group(0) if main else "", flags=re.S)
            q["text"] = norm(html.unescape(re.sub(r"<[^>]+>", " ", text)))[: max(len(p.get("text", "")), 300) + 300]
        q["url"] = base + p["url"]
        out.append(q)
    (ROOT / lang["code"] / "search-index.json").write_text(json.dumps(out, ensure_ascii=False))


def publish(offline=True, only=None, model=DEFAULT_MODEL, quiet=False):
    pages = list(english_pages())
    if not LANGS:
        return
    # search index titles/summaries are translated too
    extra = []
    si = ROOT / "search-index.json"
    if si.exists():
        for p in json.loads(si.read_text()):
            extra += [norm(html.escape(p.get(k, ""), quote=False)) for k in ("title", "summary", "type") if p.get(k)]
    needed = set(JS_STRINGS) | {k for k in extra if k}
    for _, src in pages:
        needed.update(collect(src))
    needed.discard("")

    key, spent, report = None, 0.0, []
    for lang in LANGS:
        code = lang["code"]
        if only and code not in only:
            continue
        tm = load_tm(code)
        if not offline:
            key = key or api_key()
            cost, failed = translate_missing(code, tm, sorted(needed), key, model)
            spent += cost
            if failed:
                print(f"  {code}: {len(failed)} segments could not be translated cleanly and stay in English for now.")
            save_tm(code, tm, needed)
        out_dir = ROOT / code
        if out_dir.exists():
            shutil.rmtree(out_dir)
        rendered = {}
        for rel, src in pages:
            doc = add_alternates(localize(src, rel, lang, tm), url_of(rel))
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(doc)
            rendered[url_of(rel)] = doc
        if si.exists():
            search_index(lang, tm, rendered)
        missing = sum(1 for s in needed if s not in tm)
        report.append(f"{code}: {len(pages)} pages" + (f", {missing} segments still in English" if missing else ""))

    # hreflang on the English pages and every language in the sitemap
    for rel, src in pages:
        (ROOT / rel).write_text(add_alternates(src, url_of(rel)))
    sm = ROOT / "sitemap.xml"
    if sm.exists():
        site = SITE["url"].rstrip("/")
        locs = [l for l in re.findall(r"<loc>([^<]+)</loc>", sm.read_text()) if not re.match(re.escape(site) + "/(" + "|".join(lg["code"] for lg in LANGS) + ")/", l)]
        all_locs = locs + [l.replace(site, f"{site}/{lg['code']}", 1) for lg in LANGS for l in locs]
        sm.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                      + "".join(f"<url><loc>{l}</loc></url>" for l in all_locs) + "</urlset>\n")
    if not quiet or any("still in English" in r for r in report):
        print("Languages: " + "; ".join(report))
        if any("still in English" in r for r in report) and offline:
            print("  Run  python3 translate.py  to translate the new text.")
    if spent:
        print(f"Translation cost: ${spent:.4f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="publish from saved translations only")
    ap.add_argument("--only", nargs="*", help="language codes to work on, e.g. --only de fr")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--count", action="store_true", help="show how much text would be translated, then stop")
    a = ap.parse_args()
    if a.count:
        needed = set(JS_STRINGS)
        for _, src in english_pages():
            needed.update(collect(src))
        needed.discard("")
        chars = sum(len(s) for s in needed)
        print(f"{len(needed)} unique segments, {chars:,} characters (~{chars // 4:,} tokens) per language")
        for lang in LANGS:
            tm = load_tm(lang["code"])
            print(f"  {lang['code']}: {sum(1 for s in needed if s not in tm)} not yet translated")
        sys.exit()
    publish(offline=a.offline, only=a.only, model=a.model)
