#!/usr/bin/env python3
"""Generate the site's photos with an OpenRouter image model.

Uses the same key as generate_videos.py (OPENROUTER_API_KEY or the private .env).

    python3 generate_images.py --dry-run          # plan + estimate, spends nothing
    python3 generate_images.py --yes              # generate all missing images
    python3 generate_images.py --only story-3 --force --yes   # redo one
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from generate_videos import API, ROOT, ApiError, _request, load_env_key, show_account

JOBS_FILE = ROOT / "image-jobs.json"
EST_PER_IMAGE = 0.04  # Gemini 2.5 Flash Image: ~1,290 output tokens at $30/M


def extract_image(resp):
    """Return raw image bytes from an OpenRouter chat-completions image response."""
    msg = (resp.get("choices") or [{}])[0].get("message", {})
    for img in msg.get("images") or []:
        url = (img.get("image_url") or {}).get("url", "")
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
        if url.startswith("http"):
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
    raise ApiError(f"no image in response (finish_reason={((resp.get('choices') or [{}])[0]).get('finish_reason')}, "
                   f"text={str(msg.get('content'))[:200]!r})")


def save_jpeg(data, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".src")
    tmp.write_bytes(data)
    # convert whatever came back (PNG/WebP/JPEG) to a web-friendly JPEG, max 2400px wide
    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", "1600", str(tmp), "--out", str(dest)],
                   check=True, capture_output=True)
    tmp.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--new-key", action="store_true", help="enter a new OpenRouter key (hidden) and save it to .env")
    args = ap.parse_args()

    cfg = json.loads(JOBS_FILE.read_text())
    model = args.model or cfg["model"]
    jobs = cfg["jobs"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        jobs = [j for j in jobs if j["id"] in wanted]
    todo = [j for j in jobs if args.force or not (ROOT / j["output"]).exists()]
    print(f"Model: {model}\nImages to generate: {len(todo)} (skipping {len(jobs) - len(todo)} that exist)")
    for j in todo:
        print(f" - {j['id']:18} {j['aspect_ratio']:5} -> {j['output']}")
    est = EST_PER_IMAGE * len(todo)
    print(f"Estimated cost: ~${est:.2f}")
    if args.dry_run or not todo:
        return 0

    key = "" if args.new_key else (os.environ.get("OPENROUTER_API_KEY", "").strip() or load_env_key())
    if not key and sys.stdin.isatty():
        import getpass, re
        key = getpass.getpass("Paste your NEW OpenRouter API key (hidden), then press Enter: ").strip()
        half = len(key) // 2
        if len(key) % 2 == 0 and key[:half] == key[half:]:
            key = key[:half]
            print("(It was pasted twice; kept one copy.)")
        if not re.fullmatch(r"sk-or-v1-[0-9a-f]{64}", key):
            sys.exit("That doesn't look like an OpenRouter key (expected sk-or-v1- followed by 64 characters).")
        env = ROOT / ".env"
        env.write_text(f"OPENROUTER_API_KEY={key}\n")
        os.chmod(env, 0o600)
        print("Saved new key to .env")
    if not key:
        sys.exit("No OpenRouter key: set OPENROUTER_API_KEY or create .env")
    left = show_account(key)
    if left is not None and left < est:
        sys.exit("Not enough credit.")
    if not args.yes and input("Generate now? [y/N] ").strip().lower() not in ("y", "yes"):
        return 0

    failures = 0
    for j in todo:
        body = {
            "model": model,
            "messages": [{"role": "user", "content": f"{j['prompt']} {cfg['style']}"}],
            "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": j["aspect_ratio"]},
        }
        print(f"▶ {j['id']} ...", end=" ", flush=True)
        for attempt in (1, 2, 3):
            try:
                resp = _request("POST", f"{API}/chat/completions", key=key, body=body, timeout=300)
                save_jpeg(extract_image(resp), ROOT / j["output"])
                cost = (resp.get("usage") or {}).get("cost")
                print(f"✓ saved" + (f" (${cost:.3f})" if isinstance(cost, (int, float)) else ""))
                break
            except (ApiError, subprocess.CalledProcessError) as e:
                if "HTTP 401" in str(e) or "HTTP 402" in str(e):
                    print(f"✗ {e}")
                    sys.exit("Stopping: the key was rejected or credit ran out. Nothing else was attempted.")
                if attempt == 3:
                    failures += 1
                    print(f"✗ {e}")
                else:
                    print(f"retry {attempt}...", end=" ", flush=True)
    print(f"\nDone: {len(todo) - failures} saved, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
