#!/usr/bin/env python3
"""Write a Traktor playlist (.nml) from a list of tracks.

WHY IT WRITES A COLLECTION TOO: a playlist file that only lists paths relies on
every record already being in Traktor's collection. Including a COLLECTION entry
per track means the file imports cleanly even for a record Traktor has not seen,
and carries the BPM and key with it.

THE PATH FORMAT IS THE WHOLE TRICK. Traktor stores a location as a VOLUME plus a
directory written with "/:" between the parts, and the playlist refers to it as
"VOLUME/:dir/:file". An external disk is its own volume, so /Volumes/T7/x
becomes VOLUME="T7" DIR="/:x". Get this wrong and Traktor imports a playlist of
question marks.

HOW TO TWEAK: BOOT_VOLUME is the name of the startup disk as Traktor writes it —
check an existing collection.nml if it was ever renamed.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

BOOT_VOLUME = "Macintosh HD"

_NOTE_TO_PC = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5,
               "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10,
               "bb": 10, "b": 11}
# EXACTLY HOW TRAKTOR SPELLS THEM — read out of the owner's own collection.nml,
# not chosen. It is not one convention: the same pitch is "Db" in major but
# "C#m" in minor, and "Ab" in major but "G#m" in minor.
_MAJ_NAME = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
_MIN_NAME = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]


def traktor_key(key_text: str | None) -> tuple[int | None, str]:
    """('A#-Minor') -> (21, 'Bbm'). Traktor numbers major 0..11, minor 12..23."""
    if not key_text:
        return None, ""
    text = str(key_text).strip().lower().replace(" ", "-")
    minor = "min" in text
    pc = _NOTE_TO_PC.get(text.split("-")[0].strip())
    if pc is None:
        return None, ""
    # Traktor writes minor with an "m" and major with nothing at all — checked
    # against the owner's own collection.nml, not assumed.
    return ((pc + 12, _MIN_NAME[pc] + "m") if minor else (pc, _MAJ_NAME[pc]))


def _location(path: str) -> tuple[str, str, str]:
    """(volume, dir_in_traktor_form, filename)"""
    p = Path(path)
    parts = p.parts
    if len(parts) > 2 and parts[1] == "Volumes":
        volume, rest = parts[2], parts[3:-1]
    else:
        volume, rest = BOOT_VOLUME, parts[1:-1]
    return volume, "/:" + "".join(seg + "/:" for seg in rest), p.name


def write(tracks: list[dict], out_path: str | Path, playlist_name: str) -> Path:
    """`tracks` need: path, artist, title, bpm, key, seconds. Extra keys ignored."""
    today = _dt.date.today()
    stamp = f"{today.year}/{today.month}/{today.day}"
    uuid = hashlib.md5(f"{playlist_name}{stamp}".encode()).hexdigest()

    entries, keys = [], []
    for t in tracks:
        volume, folder, filename = _location(t["path"])
        keyval, keyname = traktor_key(t.get("key"))
        info = [f'PLAYTIME="{int(t.get("seconds") or 0)}"',
                f'PLAYTIME_FLOAT="{float(t.get("seconds") or 0):.6f}"',
                f'IMPORT_DATE="{stamp}"', 'FLAGS="12"']
        if keyname:
            info.insert(0, f"KEY={quoteattr(keyname)}")
        body = [
            f"<ENTRY MODIFIED_DATE={quoteattr(stamp)} TITLE={quoteattr(t.get('title') or filename)}"
            f" ARTIST={quoteattr(t.get('artist') or '')}>",
            f"<LOCATION DIR={quoteattr(folder)} FILE={quoteattr(filename)}"
            f" VOLUME={quoteattr(volume)} VOLUMEID={quoteattr(volume)}></LOCATION>",
            '<MODIFICATION_INFO AUTHOR_TYPE="user"></MODIFICATION_INFO>',
            "<INFO " + " ".join(info) + "></INFO>",
        ]
        if t.get("bpm"):
            body.append(f'<TEMPO BPM="{float(t["bpm"]):.6f}" BPM_QUALITY="100.000000"></TEMPO>')
        if keyval is not None:
            body.append(f'<MUSICAL_KEY VALUE="{keyval}"></MUSICAL_KEY>')
        body.append("</ENTRY>")
        entries.append("\n".join(body))
        keys.append(f"{volume}{folder}{filename}")

    plist = "\n".join(
        f"<ENTRY><PRIMARYKEY TYPE=\"TRACK\" KEY={quoteattr(k)}></PRIMARYKEY></ENTRY>" for k in keys)

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
        '<NML VERSION="19"><HEAD COMPANY="www.native-instruments.com" PROGRAM="Traktor"></HEAD>\n'
        "<MUSICFOLDERS></MUSICFOLDERS>\n"
        f'<COLLECTION ENTRIES="{len(entries)}">\n' + "\n".join(entries) + "\n</COLLECTION>\n"
        '<SETS ENTRIES="0"></SETS>\n'
        '<PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="1">'
        f"<NODE TYPE=\"PLAYLIST\" NAME={quoteattr(playlist_name)}>"
        f'<PLAYLIST ENTRIES="{len(keys)}" TYPE="LIST" UUID="{uuid}">\n' + plist +
        "\n</PLAYLIST>\n</NODE>\n</SUBNODES>\n</NODE>\n</PLAYLISTS>\n</NML>\n"
    )
    out = Path(out_path)
    out.write_text(xml, encoding="utf-8")
    return out
