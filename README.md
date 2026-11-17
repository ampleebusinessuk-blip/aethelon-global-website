# Aethelon Global website

A fast static website: plain HTML, CSS and JavaScript. Pages are generated from the files in `content/` by `build.py` (Python 3, no installs).

## Preview locally

```bash
python3 -m http.server 5173
```
Then open http://localhost:5173

## Add a blog post (Insights)

1. Copy any file in `content/posts/` and rename it, e.g. `content/posts/my-new-post.md`.
2. Edit the top section (title, slug, date, category, author, excerpt, image, readtime) and write the article below it in Markdown (`## Heading`, paragraphs, `- lists`, `**bold**`, `> quote`, `[link](/contact/)`).
3. Run `python3 build.py`.

The post appears on /insights/, the home page feed, site search, the RSS feed (/insights/feed.xml) and the sitemap. New categories become filter buttons automatically.

## Add a customer story
Same as posts, in `content/stories/` (see an existing file for the fields, including `metrics:` and `quote:`).

## Edit other content
| What | File |
|---|---|
| Company name, emails, offices, values, benefits | `content/site.json` |
| Services (9 pages) | `content/services.json` |
| Industries (9 pages) | `content/industries.json` |
| Job openings | `content/careers.json` |
| Home page | `index.html` (header, footer and feed are refreshed by build.py) |

Always run `python3 build.py` after editing. It also reports any broken internal links.

## Forms
Contact and job-application forms validate input, then open the visitor's email app with the message ready to send to the address in `site.json`. To receive submissions directly instead, add `data-endpoint="https://…"` to the form (e.g. a Formspree or Netlify Forms URL) — the script posts there and falls back to email if it fails.

## Images and videos
- `python3 generate_images.py` — photos from `image-jobs.json` (OpenRouter)
- `python3 generate_videos.py` — hero videos from `video-jobs.json` (OpenRouter)
Your key lives in `.env` (never upload or share this file).

## Before launch — please review
- `content/site.json`: replace the TODO office details and confirm the email addresses.
- `content/stories/*`: these are **sample** case studies with anonymous clients and illustrative figures. Replace them with real, approved client stories before going live.
- `/privacy/`, `/cookies/`, `/terms/`, `/accessibility/`: starting templates — have them reviewed by a legal professional.
- Social links in `site.json` point to the platforms' home pages; add your real profile URLs.

## Deploy
Upload the whole folder (except `.env`, `content/`, the `*.py` scripts, `video-jobs.json`, `image-jobs.json` and `assets/videos/generation-log.jsonl` — but **do** upload `search-index.json`, which site search needs) to any static host — Netlify, Vercel, Cloudflare Pages, GitHub Pages or your web server. The site must be served from the domain root (`/`).

## Languages

The site is published in English (`/`), German (`/de/`), French (`/fr/`), Spanish (`/es/`), Arabic (`/ar/`, right-to-left) and Hindi (`/hi/`).

- `python3 build.py` builds English and republishes every language from the saved translations (no API calls).
- `python3 translate.py` sends only new or changed English text to OpenRouter, saves it, then republishes. Run it after editing content. It costs roughly $0.10 per language for the whole site and much less for small changes.
- `python3 translate.py --count` shows how much text is waiting to be translated.
- To correct a translation, edit the value in `translations/<lang>.json` and run `python3 build.py`. Your edit is kept until the English text changes.
- To add or remove a language, edit `"languages"` in `content/site.json`, add it to `LANG_NAMES` in `translate.py`, and add a link for it in `"regions"` so it appears in the picker.
- Machine translation is a strong first draft. Have a native speaker review key pages, especially the legal pages, before launch.

## Deploying with Coolify

The site is plain static files served by nginx in a small Docker image (`Dockerfile`, `nginx.conf`).

1. In Coolify: **New resource → Public/Private Repository**, pick this repo and the `main` branch.
2. **Build pack: Dockerfile** (Coolify finds `Dockerfile` at the repo root). Port: **80**.
   Or choose **Docker Compose** and Coolify will use `docker-compose.yml` instead.
3. Add your domain (e.g. `https://aethelonglobal.com`) and deploy. Coolify issues the HTTPS certificate.
4. Health check: `/healthz` returns `ok`.

To publish changes: edit content, run `python3 build.py` (and `python3 translate.py` if you changed visible text),
commit, and push. Coolify redeploys on push if auto-deploy is on.

Notes
- The image contains only the built site; source files, `content/`, `translations/`, scripts and `.env` are left out by `.dockerignore`.
- Old addresses from the previous site (`/about.html`, `/blog/...`, `/services/*.html`) redirect to the new pages.
- `.env` (your OpenRouter key) is never committed; it's listed in `.gitignore`.
