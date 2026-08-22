#!/usr/bin/env python3
"""Cloud watchdog: terminate RunPod pods that outlive their time box.

WHY THIS EXISTS SEPARATELY FROM pod_reaper.py
`pod_reaper.py` is the good guard — it can see the results files and tell a
working pod from a stuck one. But it runs on the owner's Mac. With the laptop
shut, closed or asleep, NOTHING watches the account, and a pod that fails to
self-terminate bills until someone notices. This runs on GitHub Actions instead,
so it keeps watching while the Mac is off.

WHAT IT CAN AND CANNOT JUDGE — stated plainly, because the difference matters:
it has no access to the results files, so it CANNOT tell working from stuck. It
therefore enforces one rule only, the hard time box: a pod older than
MAX_POD_MINUTES is terminated, whatever it claims to be doing. A healthy shard
finishes in ~60 minutes, so the box is set well above that and only ever catches
pods that are genuinely lost.

Foreign pods (anything not named music-db-*) get a longer box and are always
logged, because a differently-named pod once billed ~2.5 h unwatched simply
because nothing looked at it.

CREDENTIALS: reads RUNPOD_API_KEY from the environment (a GitHub secret in CI).
Locally it falls back to the runpodctl config file. The key is never printed —
not in logs, not in errors.

HOW TO TWEAK: MAX_POD_MINUTES is the box. --dry-run shows verdicts and kills
nothing.

API (verified against docs.runpod.io, Aug 2026):
  GET    https://rest.runpod.io/v1/pods
  DELETE https://rest.runpod.io/v1/pods/{podId}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://rest.runpod.io/v1"
MAX_POD_MINUTES = 120        # shard pods: ~60 min is healthy, so this is lost-only
FOREIGN_POD_MINUTES = 180    # not ours; still must not bill forever
OURS = "music-db-"


def api_key() -> str:
    key = (os.environ.get("RUNPOD_API_KEY") or "").strip()
    if key:
        return key
    config = Path.home() / ".runpod" / "config.toml"
    if config.is_file():
        # The value may be wrapped in EITHER quote style. An earlier pattern only
        # stripped double quotes, so a single-quoted key came back with the
        # quotes still attached — 52 characters instead of 50 — and every API
        # call returned a bare 401 that looked like a permissions problem.
        match = re.search(r"""(?im)^\s*api_?key\s*=\s*['"]?([^'"\s]+)['"]?""", config.read_text())
        if match:
            return match.group(1)
    sys.exit("RUNPOD_API_KEY is not set (and no runpodctl config found)")


def call(method: str, path: str, key: str):
    request = urllib.request.Request(f"{API}{path}", method=method,
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", "replace")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        # Never let the key reach a log line, even inside an error body.
        detail = exc.read().decode("utf-8", "replace")[:300].replace(key, "***")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from None


def age_minutes(pod: dict) -> float | None:
    stamp = pod.get("lastStartedAt") or pod.get("createdAt")
    if not stamp:
        return None
    text = str(stamp).strip()
    # RunPod returns Go's default time format — "2026-08-22 13:39:29.676 +0000
    # UTC" — which fromisoformat cannot parse. Handling only ISO made every pod
    # report "age unknown", so the guard kept everything and protected nothing:
    # a watchdog that never fires is not a watchdog.
    for parse in (
        lambda t: datetime.fromisoformat(t.replace("Z", "+00:00")),
        lambda t: datetime.strptime(t.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S.%f %z"),
        lambda t: datetime.strptime(t.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S %z"),
    ):
        try:
            started = parse(text)
            break
        except ValueError:
            continue
    else:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - started).total_seconds() / 60


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-minutes", type=float, default=MAX_POD_MINUTES)
    args = ap.parse_args()
    key = api_key()

    pods = call("GET", "/pods", key)
    if isinstance(pods, dict):
        pods = pods.get("data") or pods.get("pods") or []
    live = [p for p in pods if str(p.get("desiredStatus", "")).upper() != "TERMINATED"]
    print(f"{len(live)} live pod(s)")
    if not live:
        print("nothing running — nothing to bill")
        return

    killed = spend = 0.0
    for pod in live:
        name, pod_id = str(pod.get("name") or "?"), str(pod.get("id") or "")
        cost = float(pod.get("costPerHr") or 0)
        spend += cost
        age = age_minutes(pod)
        box = args.max_minutes if name.startswith(OURS) else FOREIGN_POD_MINUTES
        shown = f"{age:.0f}" if age is not None else "unknown"
        if age is None:
            # No timestamp means we cannot prove it is overdue. Log loudly and
            # leave it: killing on missing data would destroy healthy work.
            print(f"  KEEP {name} ({pod_id}) ${cost}/hr — age unknown, not judging")
            continue
        if age > box:
            print(f"  KILL {name} ({pod_id}) ${cost}/hr — {shown} min old, past the {box:.0f} min box")
            if not args.dry_run:
                try:
                    call("DELETE", f"/pods/{pod_id}", key)
                    killed += 1
                except RuntimeError as exc:
                    print(f"       terminate FAILED: {exc}")
        else:
            print(f"  OK   {name} ({pod_id}) ${cost}/hr — {shown} min old, box {box:.0f}")
    print(f"total spend now ${spend:.3f}/hr; terminated {killed:.0f}"
          + (" (dry run)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
