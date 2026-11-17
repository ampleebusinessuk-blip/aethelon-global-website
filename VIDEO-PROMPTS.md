# AI video prompts for the hero carousel

## Fastest way: generate everything with OpenRouter

```bash
export OPENROUTER_API_KEY=sk-or-...           # your key; never put it in a file
python3 generate_videos.py --dry-run          # shows the plan and cost, spends nothing
python3 generate_videos.py                    # asks to confirm, then generates all clips
```

- Prompts, lengths and models live in `video-jobs.json` — edit there, not in the script.
- Everything uses the cheapest suitable model, `google/veo-3.1-lite` at 720p:
  background loops without sound ($0.03/s), the two 8-second "Watch video" films with
  sound ($0.05/s). Estimated total for everything: about **$1.82**.
- Check your remaining credit: `python3 generate_videos.py --account`
  (the script also checks it before generating and stops if credit is too low).
- Sharper hero loops later: `--only hero-1 --force` after setting that job's
  `"resolution": "1080p"` in `video-jobs.json` ($0.05/s).
- Redo one clip: `python3 generate_videos.py --only hero-2 --force`
- Try a better model for one clip: `python3 generate_videos.py --only hero-1 --force --model google/veo-3.1-fast`
- See every available model: `python3 generate_videos.py --list-models`
- Each clip takes roughly 30 seconds to a few minutes. Finished clips are skipped on re-runs.
- If a run is interrupted after submitting, recover it with `--fetch JOB_ID --only hero-N`
  (job IDs are printed and logged to `assets/videos/generation-log.jsonl`).

## Manual way: any AI video tool

Generate each clip with an AI video tool (Veo, Runway, Kling, Seedance, Luma, etc.),
export as **MP4 (H.264), 1920×1080, no audio**, and save it under the file name shown.
The site picks the files up automatically; until then each slide shows an animated stand-in.

The coloured ribbon shapes, word-pills and lines are **added by the website code on top**
of the footage, so do **not** ask the AI tool for graphics or text. Ask only for plain,
live-action footage.

Shared style for every clip (paste at the end of each prompt):

> Photorealistic documentary-style footage, natural window light, warm and soft,
> shallow depth of field, 35mm lens, gentle handheld or slow dolly movement,
> candid and unposed, diverse real-looking people, modern but lived-in spaces
> with plants and wood, muted warm colour grade, no text, no logos, no graphics,
> seamless loop.

| Slide | Save as | Length |
|---|---|---|
| 1 | `assets/videos/hero-1.mp4` | 4–6 s loop |
| 2 | `assets/videos/hero-2.mp4` | 4–6 s loop |
| 3 | `assets/videos/hero-3.mp4` | 8–10 s loop |
| 4 | `assets/videos/hero-4.mp4` | 6–8 s loop |
| 5 | `assets/videos/hero-5.mp4` | 4–6 s loop |
| "Watch video" film (slide 1) | `assets/videos/film-ai.mp4` | 20–40 s |
| "Watch video" film (slide 5) | `assets/videos/film-legacy.mp4` | 30–60 s |
| Slide 6 still image | `assets/images/hero-6.jpg` | 2560×1440 photo |

Also export one still frame per clip as a poster (`hero-1.jpg` … `hero-5.jpg` in
`assets/images/`) — it shows instantly while the video loads and on slow connections.

---

## Slide 1 — "AI in motion" (relaxed, joyful portrait)
A woman in her late twenties with short tousled blonde hair, wearing a loose mustard-yellow
shirt, leans back in a grey upholstered lounge chair in a sunlit room, laughing softly and
touching her chin, eyes half-closed. Warm afternoon sun streams across her face through
slatted blinds, a large green houseplant in the foreground edge of frame. Camera is slightly
above, slowly drifting right. [shared style]

## Slide 2 — "Meet your customers in the moments that matter" (focused at a desk)
A woman in her thirties with dark hair tied back and round tortoiseshell glasses, wearing a
terracotta linen shirt, sits at a wooden table by a tall window in a cosy apartment, writing
in a notebook with a pen and glancing at an open laptop. Hanging Edison bulb, plants and a
softly blurred doorway behind her. Camera slowly pushes in from behind the laptop screen,
which is out of focus in the foreground. [shared style]

## Slide 3 — "AI accelerates teams" (team with motion blur)
High-angle shot of a small team in a plant-filled studio office with exposed brick and large
windows. A young South Asian woman in a navy jumper with thin red stripes sits at a desk with
a tablet, listening intently to a colleague in a brown sweater seated across from her.
Another colleague walks quickly through the foreground, rendered as a long-exposure motion
blur streak, while the seated people stay sharp. Slow, steady camera. [shared style]

## Slide 4 — "2026 outlook" (strategy meeting)
Side-on shot of a meeting at a long table in a bright, minimal concrete-walled room with a
floor-to-ceiling window overlooking city buildings. In the foreground a Black man with
glasses and a dark turtleneck rests his hand thoughtfully at his chin; behind him a woman
with a short platinum bob and clear-frame glasses in a white blouse listens, pen in hand,
papers with charts on the table, a black coffee mug. Cool daylight, slight slow dolly left.
[shared style, but cooler daylight grade]

## Slide 5 — "Zero legacy" (comedic office celebration)
A cheerful open-plan office decorated with colourful balloons. Several colleagues in business
casual dance and celebrate with exaggerated joy around a large, old-fashioned beige
refrigerator-sized computer server cabinet that is being wheeled away, as if retiring it.
A man in a light checked shirt does an awkward happy dance in the centre, a woman in an
olive-green suit gasps with delight, an older man in a navy blazer cheers. Bright, upbeat,
slightly comedic commercial feel, handheld. [shared style, brighter and more saturated]

## Film — `film-ai.mp4` ("Watch video" on slide 1)
A 30-second brand-style montage: quick, rhythmic cuts between people collaborating at
whiteboards, a developer smiling at code on a monitor, a customer-service agent helping
someone on a headset, a doctor reviewing a tablet with a patient, a retail worker using a
handheld scanner, ending on a wide shot of a team laughing together at sunset by a window.
[shared style]

## Film — `film-legacy.mp4` ("Watch video" on slide 5)
A 45-second comedic short: an office team holds a mock "retirement party" for an enormous
outdated server cabinet — a speech, a cake with a candle placed on top of the cabinet, people
hugging it goodbye, then it is wheeled out the door to applause and the team turns to a sleek
laptop with relief. Light, playful commercial tone. [shared style, brighter]

## Slide 6 still image — `hero-6.jpg`
Photo: two colleagues at a standing desk in a modern, plant-filled office looking at a large
monitor showing colourful (non-legible) charts, one pointing, both engaged and smiling,
warm window light, shallow depth of field, room on the left side of the frame for headline
text. No text or logos.
