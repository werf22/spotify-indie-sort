"""
Classifies every track in data/library_export.json as keep (Indie/listening
music) or exclude (afro/organic/shamanic house, ecstatic-dance grooves), per
the taste line in genre_line.py.

Needs ANTHROPIC_API_KEY in .env. Batches tracks and calls Claude directly
(not the `claude` CLI — shelling out to it needs an interactively-logged-in
session, which a cron'd re-run won't have).

Output: data/classification.json — [{id, decision, reason}, ...]
"""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv

from genre_line import BOUNDARY_DESCRIPTION, KEEP_EXAMPLES

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
IN_PATH = DATA_DIR / "library_export.json"
OUT_PATH = DATA_DIR / "classification.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = "claude-fable-5"  # standing rule: all work runs on the top-tier model
BATCH_SIZE = int(os.getenv("CLASSIFY_BATCH_SIZE", "60"))
CONCURRENCY = 4


def log(msg: str) -> None:
    print(f"[classify] {msg}", flush=True)


def build_prompt(batch: list[dict]) -> str:
    examples = "\n".join(f'- "{title}" by {artist}' for artist, title in KEEP_EXAMPLES)
    tracks_json = json.dumps(
        [
            {
                "id": t["id"],
                "name": t["name"],
                "artists": [a["name"] for a in t["artists"]],
                "genres": t.get("genres", []),
            }
            for t in batch
        ],
        ensure_ascii=False,
    )
    return f"""You are sorting a DJ's Spotify library into a "keep" (Indie / normal
listening music) playlist vs everything else.

{BOUNDARY_DESCRIPTION}

Reference tracks the owner confirmed as KEEP:
{examples}

Classify each track below. Respond with ONLY a JSON array, no prose, no
markdown fences: [{{"id": "...", "decision": "keep"|"exclude", "reason": "<8 words max>"}}, ...]
One entry per input track, same id values.

Tracks:
{tracks_json}"""


def classify_batch(batch: list[dict]) -> list[dict]:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": build_prompt(batch)}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    result = json.loads(text)
    if len(result) != len(batch):
        raise ValueError(f"batch size {len(batch)} but got {len(result)} decisions back")
    return result


def main() -> None:
    if not ANTHROPIC_API_KEY:
        log("FAILED: ANTHROPIC_API_KEY not set in .env — see .env.example")
        sys.exit(1)

    tracks = json.loads(IN_PATH.read_text())
    batches = [tracks[i : i + BATCH_SIZE] for i in range(0, len(tracks), BATCH_SIZE)]
    log(f"{len(tracks)} tracks in {len(batches)} batches of {BATCH_SIZE}, {CONCURRENCY} at a time")

    results: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(classify_batch, b): b for b in batches}
        for fut in as_completed(futures):
            batch = futures[fut]
            try:
                results.extend(fut.result())
            except Exception as e:  # noqa: BLE001
                ids = [t["id"] for t in batch]
                log(f"batch FAILED ({e!r}), marking {len(ids)} tracks as keep (safe default)")
                results.extend({"id": i, "decision": "keep", "reason": "batch error, defaulted"} for i in ids)
            done += 1
            log(f"  ...{done}/{len(batches)} batches done")

    OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    kept = sum(1 for r in results if r["decision"] == "keep")
    log(f"wrote {OUT_PATH}: {kept} keep / {len(results) - kept} exclude")


if __name__ == "__main__":
    main()
