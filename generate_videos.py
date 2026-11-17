#!/usr/bin/env python3
"""Generate the site's hero videos with OpenRouter's video API.

Reads video-jobs.json, checks each job against the chosen model's supported
durations / resolutions / aspect ratios, prints a cost estimate, then submits,
polls and downloads each clip into assets/videos/.

Usage:
    export OPENROUTER_API_KEY=sk-or-...        # never paste the key into files
    python3 generate_videos.py --dry-run         # plan + cost estimate, spends nothing
    python3 generate_videos.py                   # generate everything missing
    python3 generate_videos.py --only hero-1     # just one clip
    python3 generate_videos.py --only hero-1 --force   # regenerate (overwrite)
    python3 generate_videos.py --model bytedance/seedance-2.0   # try another model
    python3 generate_videos.py --list-models     # show available video models

Only Python's standard library is used.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://openrouter.ai/api/v1"
ROOT = Path(__file__).resolve().parent
JOBS_FILE = ROOT / "video-jobs.json"
POLL_SECONDS = 15
TIMEOUT_SECONDS = 20 * 60
TERMINAL_FAIL = {"failed", "cancelled", "expired"}


# ---------- HTTP helpers ----------

def _request(method, url, key=None, body=None, raw=False, timeout=120):
    headers = {"Accept": "application/json", "User-Agent": "aethelon-site-video-generator/1.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            return payload if raw else json.loads(payload or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:800]
        try:
            j = json.loads(detail)
            detail = j.get("error", {}).get("message") if isinstance(j.get("error"), dict) else j.get("error") or detail
        except ValueError:
            pass
        raise ApiError(f"HTTP {e.code} from {url.split('?')[0]}: {detail}") from None
    except urllib.error.URLError as e:
        raise ApiError(f"Network error reaching {url.split('?')[0]}: {e.reason}") from None


class ApiError(Exception):
    pass


def load_env_key():
    """Read OPENROUTER_API_KEY from a private .env file next to this script, if present."""
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:]
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def absolute(url):
    return url if url.startswith("http") else "https://openrouter.ai" + (url if url.startswith("/") else "/" + url)


# ---------- Model capabilities ----------

def fetch_models(key):
    data = _request("GET", f"{API}/videos/models", key=key)
    return {m["id"]: m for m in data.get("data", []) if "id" in m}


def nearest(value, allowed, numeric=False):
    """Return value if allowed, else the closest allowed option (or None if no list)."""
    if not allowed:
        return value
    if value in allowed:
        return value
    if numeric:
        return min(allowed, key=lambda a: (abs(a - value), -a))
    return allowed[0]


def show_account(key):
    """Print remaining OpenRouter credit; returns remaining dollars or None."""
    remaining = None
    try:
        d = _request("GET", f"{API}/credits", key=key).get("data", {})
        total, used = float(d.get("total_credits", 0)), float(d.get("total_usage", 0))
        remaining = total - used
        print(f"Account credits: ${total:.2f} bought, ${used:.2f} used, ${remaining:.2f} left")
    except (ApiError, TypeError, ValueError) as e:
        print(f"! Could not read account credits ({e})")
    try:
        k = _request("GET", f"{API}/key", key=key).get("data", {})
        lim, rem = k.get("limit"), k.get("limit_remaining")
        if lim is not None:
            print(f"This key's spend limit: ${float(lim):.2f}, ${float(rem or 0):.2f} remaining")
            remaining = min(remaining, float(rem or 0)) if remaining is not None else float(rem or 0)
    except (ApiError, TypeError, ValueError):
        pass
    return remaining


def resolve_job(job, caps):
    """Fit a job's settings to what the model supports; returns (settings, notes)."""
    notes = []
    durations = caps.get("supported_durations") or []
    resolutions = caps.get("supported_resolutions") or []
    aspects = caps.get("supported_aspect_ratios") or []
    d = nearest(job["duration"], durations, numeric=True)
    if d != job["duration"]:
        notes.append(f"duration {job['duration']}s -> {d}s (model allows {durations})")
    r = nearest(job["resolution"], resolutions)
    if r != job["resolution"]:
        # prefer the highest resolution up to 1080p
        pref = [x for x in ("1080p", "720p", "768p", "480p") if x in resolutions]
        r = pref[0] if pref else r
        notes.append(f"resolution {job['resolution']} -> {r} (model allows {resolutions})")
    a = nearest(job["aspect_ratio"], aspects)
    if a != job["aspect_ratio"]:
        notes.append(f"aspect {job['aspect_ratio']} -> {a} (model allows {aspects})")
    audio_cap = caps.get("generate_audio")
    audio = bool(job.get("audio", False)) and audio_cap is not False
    return {"duration": d, "resolution": r, "aspect_ratio": a, "generate_audio": audio, "audio_supported": audio_cap}, notes


RES_SUFFIX = re.compile(r"_(\d+p|\dk)$", re.I)


def estimate_cost(caps, seconds, audio, resolution):
    """Per-second price from pricing_skus matched on audio + resolution.

    SKU names look like duration_seconds_with_audio_720p; a name without a
    resolution suffix is the model's default-resolution price."""
    skus = caps.get("pricing_skus") or {}
    if isinstance(skus, list):
        skus = {s.get("sku") or s.get("name"): s.get("price") for s in skus if isinstance(s, dict)}
    cands = [(str(k), v) for k, v in skus.items() if k and "second" in str(k)]
    if any("audio" in k for k, _ in cands):
        wanted = "without_audio" if not audio else "with_audio"
        cands = [kv for kv in cands if wanted in kv[0]] or cands
    res = (resolution or "").lower()
    exact = [kv for kv in cands if kv[0].lower().endswith("_" + res)]
    default = [kv for kv in cands if not RES_SUFFIX.search(kv[0])]
    for k, v in exact or default:
        try:
            return float(v) * seconds, k
        except (TypeError, ValueError):
            continue
    return None, "price not listed for this resolution (check openrouter.ai)"


# ---------- Generation ----------

def build_prompt(cfg, job):
    style = cfg.get("style", "")
    if job.get("loop") is False:
        style = style.replace(", seamless loop", "").replace("seamless loop", "")
    return f"{job['prompt'].strip()} {style}".strip()


def submit(key, model, prompt, s):
    body = {
        "model": model,
        "prompt": prompt,
        "duration": s["duration"],
        "resolution": s["resolution"],
        "aspect_ratio": s["aspect_ratio"],
    }
    if s["audio_supported"] is not None or s["generate_audio"]:
        body["generate_audio"] = s["generate_audio"]
    return _request("POST", f"{API}/videos", key=key, body=body)


def wait_for(key, job_id, polling_url, label):
    url = absolute(polling_url) if polling_url else f"{API}/videos/{job_id}"
    start = time.time()
    last = None
    net_errors = 0
    while True:
        try:
            info = _request("GET", url, key=key)
            net_errors = 0
        except ApiError as e:
            # brief network/SSL hiccups: keep polling instead of abandoning a paid job
            if "Network error" in str(e) or "HTTP 5" in str(e) or "HTTP 429" in str(e):
                net_errors += 1
                if net_errors <= 8:
                    print(f"   [{label}] connection hiccup, retrying ({net_errors}/8)...")
                    time.sleep(POLL_SECONDS)
                    continue
            raise
        status = info.get("status")
        if status != last:
            print(f"   [{label}] status: {status}")
            last = status
        if status == "completed":
            return info
        if status in TERMINAL_FAIL:
            raise ApiError(f"job {job_id} {status}: {info.get('error') or 'no error message'}")
        if time.time() - start > TIMEOUT_SECONDS:
            raise ApiError(f"job {job_id} still '{status}' after {TIMEOUT_SECONDS // 60} min; "
                           f"check later with: python3 generate_videos.py --fetch {job_id} --only {label}")
        time.sleep(POLL_SECONDS)


def download(key, job_id, dest):
    for attempt in range(1, 5):
        try:
            data = _request("GET", f"{API}/videos/{job_id}/content?index=0", key=key, raw=True, timeout=600)
            break
        except ApiError as e:
            if attempt == 4 or "Network error" not in str(e):
                raise
            print(f"   download hiccup, retrying ({attempt}/3)...")
            time.sleep(5)
    if len(data) < 1000:
        raise ApiError(f"download for {job_id} looks empty ({len(data)} bytes)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return len(data)


def log_job(entry):
    with open(ROOT / "assets" / "videos" / "generation-log.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="show plan and cost estimate; submit nothing")
    ap.add_argument("--only", help="comma-separated job ids, e.g. hero-1,hero-3")
    ap.add_argument("--force", action="store_true", help="regenerate even if the output file exists")
    ap.add_argument("--model", help="override the model for every job")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--list-models", action="store_true", help="list available video models and exit")
    ap.add_argument("--fetch", metavar="JOB_ID", help="download an already-submitted job (use with --only)")
    ap.add_argument("--account", action="store_true", help="show remaining OpenRouter credit and exit")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY", "").strip() or load_env_key()
    cfg = json.loads(JOBS_FILE.read_text())

    if args.account:
        if not key:
            sys.exit("OPENROUTER_API_KEY is not set.")
        show_account(key)
        return 0

    try:
        models = fetch_models(key or None)
    except ApiError as e:
        models = {}
        print(f"! Could not load model capabilities ({e}). Settings will be sent unvalidated.")

    if args.list_models:
        for mid, m in sorted(models.items()):
            print(f"{mid:40} durations={m.get('supported_durations')} res={m.get('supported_resolutions')} audio={m.get('generate_audio')}")
        return 0

    jobs = cfg["jobs"]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        unknown = wanted - {j["id"] for j in jobs}
        if unknown:
            sys.exit(f"Unknown job id(s): {', '.join(sorted(unknown))}")
        jobs = [j for j in jobs if j["id"] in wanted]

    plan, total, unpriced = [], 0.0, False
    print("\nPlan:")
    for job in jobs:
        out = ROOT / job["output"]
        model = args.model or job.get("model") or cfg["default_model"]
        if out.exists() and not args.force and not args.fetch:
            print(f" - {job['id']:12} skip (exists: {job['output']}; use --force to redo)")
            continue
        caps = models.get(model)
        if models and caps is None:
            print(f" - {job['id']:12} ! model '{model}' not in OpenRouter's video model list; run --list-models")
            continue
        s, notes = resolve_job(job, caps or {})
        cost, label = estimate_cost(caps or {}, s["duration"], s["generate_audio"], s["resolution"])
        if cost is None:
            unpriced = True
        else:
            total += cost
        price = f"~${cost:.2f}" if cost is not None else "price ?"
        print(f" - {job['id']:12} {model}  {s['duration']}s {s['resolution']} {s['aspect_ratio']} "
              f"audio={'on' if s['generate_audio'] else 'off'}  {price}  -> {job['output']}")
        for n in notes:
            print(f"     note: {n}")
        plan.append((job, model, s, out))

    if not plan:
        print("\nNothing to do.")
        return 0
    print(f"\nEstimated total: ~${total:.2f}" + (" (plus jobs with unlisted prices)" if unpriced else "")
          + "  — estimates only; OpenRouter bills the actual amount.")

    if args.dry_run:
        print("Dry run: nothing submitted.")
        return 0
    if not key and sys.stdin.isatty():
        import getpass
        key = getpass.getpass("\nPaste your OpenRouter API key (input is hidden), then press Enter: ").strip()
        if key and input("Save it to the private .env file so you are not asked again? [y/N] ").strip().lower() in ("y", "yes"):
            env = ROOT / ".env"
            env.write_text(f"OPENROUTER_API_KEY={key}\n")
            os.chmod(env, 0o600)
            print("Saved to .env (readable only by you).")
    if not key:
        sys.exit("\nOPENROUTER_API_KEY is not set. Run:  export OPENROUTER_API_KEY=sk-or-...")
    left = show_account(key)
    if left is not None and left < total:
        sys.exit(f"Not enough credit (${left:.2f} left, ~${total:.2f} needed). Top up at https://openrouter.ai/settings/credits")
    if not args.yes:
        if input("\nGenerate these videos now? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return 0

    failures = 0
    for job, model, s, out in plan:
        print(f"\n▶ {job['id']} ({model})")
        job_id = None
        try:
            if args.fetch:
                job_id, polling = args.fetch, None
            else:
                resp = submit(key, model, build_prompt(cfg, job), s)
                job_id, polling = resp.get("id"), resp.get("polling_url")
                if not job_id:
                    raise ApiError(f"no job id in response: {resp}")
                print(f"   submitted job {job_id}")
            info = wait_for(key, job_id, polling, job["id"])
            size = download(key, job_id, out)
            cost = (info.get("usage") or {}).get("cost")
            print(f"   ✓ saved {job['output']} ({size / 1e6:.1f} MB)" + (f", billed ${cost}" if cost is not None else ""))
            log_job({"id": job["id"], "job_id": job_id, "model": model, "settings": s, "cost": cost, "time": int(time.time())})
        except ApiError as e:
            failures += 1
            print(f"   ✗ {e}")
            if not args.fetch and job_id:
                print(f"   Recover without paying again:  python3 generate_videos.py --fetch {job_id} --only {job['id']}")
        except KeyboardInterrupt:
            print("\nStopped. Jobs already submitted keep running on OpenRouter; re-run with --fetch JOB_ID --only ID.")
            return 130

    print(f"\nDone: {len(plan) - failures} saved, {failures} failed. Reload the site to see new videos.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
