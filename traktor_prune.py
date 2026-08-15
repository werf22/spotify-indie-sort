#!/usr/bin/env python3
"""Make every Traktor collection entry loadable: repair paths, delete the rest.

GOAL (owner, 2026-08-15): after this runs, no track in the collection may fail
to load because its file path is wrong. Anything whose audio cannot be found on
T7 or on the MacBook is removed from the collection entirely.

WHY REPAIR COMES FIRST: 34,242 of 93,842 entries point at a file that is not
there — but 28,744 of those are on T7, whose folder layout was reorganised after
the collection was written. The audio still exists under a different path.
Deleting on a failed path check alone would have thrown away ~29,000 tracks the
owner actually owns. So every broken entry is first matched by FILENAME against
what is really on disk, and only what cannot be found anywhere is deleted.

DISAMBIGUATION: when a filename occurs more than once on disk, the candidate
whose size best matches the collection's FILESIZE wins (Traktor stores it in
KB); with no usable size the largest file wins, which favours the original over
a truncated copy. Never a guess between unrelated files — the name must match.

PLAYLISTS: a deleted entry's references are removed from every playlist too,
otherwise Traktor shows the same broken track from inside the playlist.

SAFETY
  - refuses to run while Traktor is open (it would overwrite our file on quit)
  - refuses if T7 is not mounted (every T7 track would look missing)
  - refuses if deletions would exceed MAX_DELETE_RATIO of the collection
  - full timestamped backup before any write; XML validated before the swap
  - --dry-run reports everything and changes nothing

USAGE
  ./.venv/bin/python traktor_prune.py --dry-run
  ./.venv/bin/python traktor_prune.py --apply
  ./.venv/bin/python traktor_prune.py --verify
"""

from __future__ import annotations

import argparse
import collections
import html
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NML = Path("/Users/jakub/Documents/Native Instruments/Traktor 4.0.2/collection.nml")
BACKUP_DIR = ROOT / "data" / "traktor_backups"
REPORT = ROOT / "data" / "traktor_prune_report.txt"

SEARCH_ROOTS = [Path("/Volumes/T7"), Path.home() / "Music", Path.home() / "Downloads"]
AUDIO_SUFFIXES = {".mp3", ".m4a", ".flac", ".wav", ".aiff", ".aif", ".ogg",
                  ".opus", ".alac", ".wma", ".aac", ".mp4", ".m4b"}
MAX_DELETE_RATIO = 0.25      # a bigger cull means something is wrong, not dirty data


def norm(name: str) -> str:
    """macOS stores NFD on disk, the NML carries NFC — compare on one form."""
    return unicodedata.normalize("NFC", name).casefold()


def traktor_running() -> bool:
    try:
        return subprocess.run(["pgrep", "-x", "Traktor"], capture_output=True,
                              timeout=10).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def resolve(loc: str) -> tuple[Path | None, str, str]:
    """(path as the collection states it, volume, filename)."""
    get = lambda n: html.unescape((re.search(rf'{n}="([^"]*)"', loc) or [None, ""])[1])
    vol, directory, filename = get("VOLUME"), get("DIR").replace("/:", "/"), get("FILE")
    if not filename:
        return None, vol, ""
    if vol and vol.lower() not in ("macintosh hd", "macintosh hd - data"):
        return Path(f"/Volumes/{vol}{directory}{filename}"), vol, filename
    return Path(f"{directory}{filename}"), vol or "Macintosh HD", filename


def index_disk() -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = collections.defaultdict(list)
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            print(f"  (skipping {root} — not present)", flush=True)
            continue
        count = 0
        for path in root.rglob("*"):
            try:
                if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES \
                        and not path.name.startswith("._"):
                    found[norm(path.name)].append(path)
                    count += 1
            except OSError:
                continue
        print(f"  {root}: {count:,} audio files", flush=True)
    return found


def pick(candidates: list[Path], want_kb: int | None) -> Path | None:
    """Best candidate for a filename: closest size, else the largest."""
    if len(candidates) == 1:
        return candidates[0]
    sized: list[tuple[int, Path]] = []
    for candidate in candidates:
        try:
            sized.append((candidate.stat().st_size, candidate))
        except OSError:
            continue
    if not sized:
        return None
    if want_kb:
        target = want_kb * 1024
        return min(sized, key=lambda s: abs(s[0] - target))[1]
    return max(sized, key=lambda s: s[0])[1]


def location_xml(path: Path) -> str:
    """A LOCATION tag Traktor understands, for a real path on disk."""
    parts = path.parts
    if len(parts) > 2 and parts[1] == "Volumes":
        volume = parts[2]
        directory = "/" + "/".join(parts[3:-1])
    else:
        volume = "Macintosh HD"
        directory = "/" + "/".join(parts[1:-1])
    if not directory.endswith("/"):
        directory += "/"
    traktor_dir = directory.replace("/", "/:")
    esc = lambda s: html.escape(s, quote=True)
    return (f'<LOCATION DIR="{esc(traktor_dir)}" FILE="{esc(path.name)}" '
            f'VOLUME="{esc(volume)}" VOLUMEID="{esc(volume)}"></LOCATION>')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        return verify()
    if args.apply and traktor_running():
        raise SystemExit("Traktor is running — quit it first, or it will overwrite this work.")
    if not Path("/Volumes/T7").is_dir():
        raise SystemExit("T7 is not mounted — every T7 track would look missing. Aborting.")

    print("reading the collection …", flush=True)
    text = NML.read_text(encoding="utf-8", errors="replace")
    cstart, cend = text.find("<COLLECTION"), text.find("</COLLECTION>")
    if cstart < 0 or cend < 0:
        raise SystemExit("could not find the COLLECTION section")
    head, collection, tail = text[:cstart], text[cstart:cend], text[cend:]

    print("indexing what is actually on disk …", flush=True)
    disk = index_disk()
    print(f"  {sum(len(v) for v in disk.values()):,} files, "
          f"{len(disk):,} distinct names", flush=True)

    stats = collections.Counter()
    repairs: list[tuple[str, str]] = []       # (old LOCATION xml, new LOCATION xml)
    delete_keys: set[str] = set()             # PRIMARYKEY paths of removed entries
    rekey: dict[str, str] = {}                # old PRIMARYKEY -> new, for repaired paths
    deleted_names: list[str] = []

    def entry_primarykey(loc_xml: str) -> str:
        """Playlists address tracks BY PATH, in exactly this shape:
        VOLUME/:dir/:sub/:file.ext — so repairing a collection path without
        rewriting these keys would leave every playlist pointing at nothing,
        which is precisely the broken-track symptom this run must eliminate."""
        # UNESCAPE both sides. Comparing an escaped key from the collection
        # against an unescaped one from a playlist silently missed every track
        # whose path contains an apostrophe or ampersand — 22,603 references
        # were left dangling by exactly that mismatch on the first run.
        get = lambda n: html.unescape((re.search(rf'{n}="([^"]*)"', loc_xml) or [None, ""])[1])
        return f"{get('VOLUME')}{get('DIR')}{get('FILE')}"

    def handle(match: re.Match) -> str:
        entry = match.group(0)
        loc = re.search(r'<LOCATION[^>]*>(?:</LOCATION>)?', entry)
        if not loc:
            stats["no_location"] += 1
            return entry
        path, volume, filename = resolve(loc.group(0))
        if path is not None and path.is_file():
            stats["ok"] += 1
            return entry
        # Broken. Can the audio be found anywhere by name?
        candidates = disk.get(norm(filename)) if filename else None
        if candidates:
            info = re.search(r'<INFO[^>]*>', entry)
            want_kb = None
            if info:
                size = re.search(r'FILESIZE="(\d+)"', info.group(0))
                want_kb = int(size.group(1)) if size else None
            chosen = pick(candidates, want_kb)
            if chosen is not None:
                stats["repaired"] += 1
                new_loc = location_xml(chosen)
                rekey[entry_primarykey(loc.group(0))] = entry_primarykey(new_loc)
                repairs.append((loc.group(0)[:120], new_loc[:120]))
                return entry[:loc.start()] + new_loc + entry[loc.end():]
        stats["deleted"] += 1
        delete_keys.add(entry_primarykey(loc.group(0)))
        title = re.search(r'TITLE="([^"]*)"', entry)
        if len(deleted_names) < 40:
            deleted_names.append(f"{volume}: {html.unescape(title.group(1)) if title else filename}")
        return ""

    print("checking every entry …", flush=True)
    new_collection = re.sub(r'<ENTRY\b.*?</ENTRY>', handle, collection, flags=re.S)

    total = stats["ok"] + stats["repaired"] + stats["deleted"]
    print(f"\ncollection entries: {total:,}")
    print(f"  already fine:      {stats['ok']:,}")
    print(f"  PATH REPAIRED:     {stats['repaired']:,}")
    print(f"  to be DELETED:     {stats['deleted']:,}")
    if stats["no_location"]:
        print(f"  no LOCATION tag:   {stats['no_location']:,} (left untouched)")

    if total and stats["deleted"] / total > MAX_DELETE_RATIO:
        raise SystemExit(f"refusing: would delete {stats['deleted']/total:.0%} of the "
                         f"collection (limit {MAX_DELETE_RATIO:.0%}). Investigate first.")

    # Entry count in the COLLECTION header must match reality or Traktor complains.
    new_count = len(re.findall(r'<ENTRY\b', new_collection))
    new_collection = re.sub(r'(<COLLECTION\s+ENTRIES=")\d+(")',
                            rf'\g<1>{new_count}\g<2>', new_collection, count=1)

    # Playlists address tracks by path: repaired entries need their references
    # rewritten, deleted ones removed. Skipping either leaves broken tracks
    # showing inside playlists even though the collection itself is clean.
    removed_refs = rekeyed_refs = 0
    if delete_keys or rekey:
        def fix_ref(match: re.Match) -> str:
            nonlocal removed_refs, rekeyed_refs
            block = match.group(0)
            key = re.search(r'KEY="([^"]*)"', block)
            if not key:
                return block
            raw = html.unescape(key.group(1))
            if raw in delete_keys:
                removed_refs += 1
                return ""
            new_key = rekey.get(raw)
            if new_key:
                rekeyed_refs += 1
                return (block[:key.start(1)] + html.escape(new_key, quote=True)
                        + block[key.end(1):])
            return block
        tail = re.sub(r'<ENTRY>\s*<PRIMARYKEY\b.*?</ENTRY>\s*', fix_ref, tail, flags=re.S)
        # Keep each playlist's advertised size honest.
        def fix_size(match: re.Match) -> str:
            body = match.group(0)
            n = len(re.findall(r'<PRIMARYKEY\b', body))
            return re.sub(r'(<PLAYLIST\s+ENTRIES=")\d+(")', rf'\g<1>{n}\g<2>', body, count=1)
        tail = re.sub(r'<PLAYLIST\b.*?</PLAYLIST>', fix_size, tail, flags=re.S)
        print(f"  playlist references repointed: {rekeyed_refs:,}")
        print(f"  playlist references removed:   {removed_refs:,}")

    lines = [f"repaired {stats['repaired']:,} · deleted {stats['deleted']:,} · "
             f"playlist refs removed {removed_refs:,}", "", "sample repairs:"]
    lines += [f"  {a}\n    -> {b}" for a, b in repairs[:20]]
    lines += ["", "sample deletions (no file anywhere):"] + [f"  {n}" for n in deleted_names]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport written: {REPORT}")

    if not args.apply:
        print("\ndry run — the collection was not modified. Pass --apply to write.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backup = BACKUP_DIR / f"collection.before-prune.{stamp}.nml"
    shutil.copy2(NML, backup)
    print(f"backup taken: {backup.name}", flush=True)

    tmp = NML.with_suffix(".nml.tmp")
    tmp.write_text(head + new_collection + tail, encoding="utf-8")
    root = ET.parse(tmp).getroot()          # must still be well-formed XML
    kept = len(root.findall("./COLLECTION/ENTRY"))
    if kept != new_count:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"refusing to swap: parsed {kept} entries, expected {new_count}")
    tmp.replace(NML)
    print(f"collection written: {kept:,} entries remain", flush=True)
    verify()


def verify() -> None:
    """Independent proof: can every remaining entry's file be opened?"""
    print("\nVERIFYING the collection on disk …", flush=True)
    text = NML.read_text(encoding="utf-8", errors="replace")
    cstart, cend = text.find("<COLLECTION"), text.find("</COLLECTION>")
    collection = text[cstart:cend]
    total = missing = 0
    examples: list[str] = []
    for match in re.finditer(r'<ENTRY\b.*?</ENTRY>', collection, re.S):
        loc = re.search(r'<LOCATION[^>]*>', match.group(0))
        if not loc:
            continue
        total += 1
        path, volume, _ = resolve(loc.group(0))
        if path is None or not path.is_file():
            missing += 1
            if len(examples) < 5:
                examples.append(f"{volume}: {path}")
    header = re.search(r'<COLLECTION\s+ENTRIES="(\d+)"', text)
    print(f"  entries in collection: {total:,} (header says {header.group(1) if header else '?'})")
    print(f"  files present:         {total - missing:,}")
    print(f"  files MISSING:         {missing:,}")
    for e in examples:
        print(f"     {e}")

    # A playlist reference that matches no collection entry shows up in Traktor
    # as a broken track even when the collection itself is spotless.
    keys = set()
    for match in re.finditer(r'<ENTRY\b.*?</ENTRY>', collection, re.S):
        loc = re.search(r'<LOCATION[^>]*>', match.group(0))
        if loc:
            get = lambda n: (re.search(rf'{n}="([^"]*)"', loc.group(0)) or [None, ""])[1]
            keys.add(html.unescape(f"{get('VOLUME')}{get('DIR')}{get('FILE')}"))
    tail = text[cend:]
    refs = re.findall(r'<PRIMARYKEY[^>]*KEY="([^"]*)"', tail)
    dangling = [k for k in (html.unescape(r) for r in refs) if k not in keys]
    print(f"  playlist references:   {len(refs):,}")
    print(f"  dangling references:   {len(dangling):,}")
    for d in dangling[:3]:
        print(f"     {d[:100]}")

    print("\nVERDICT:", "every entry and every playlist reference resolves to a real file"
          if missing == 0 and not dangling else "STILL BROKEN — do not hand this over")


if __name__ == "__main__":
    main()
