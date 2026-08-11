#!/usr/bin/env python3
"""Transparent reader for shard result files, plain or gzipped.

WHAT: `open_jsonl(path)` yields a text handle for `path`, or for `path.gz` when
the plain file is gone — so every consumer keeps working after a finished shard
is compressed.

WHY: the per-window timelines in `results.jsonl` are the raw material for
zero-cost validation studies (window-budget, fp16), so they must be KEPT, but
uncompressed they grew to 19.9 GiB and tripped the disk guard that pauses clip
preparation. JSON compresses ~8x, so archiving imported shards buys back the
headroom without losing a single window.

HOW TO TWEAK: `compress_results()` is only ever called on a shard that has
already imported; never compress a file the runner may still append to, since
the incremental byte-offset pull in runpod_full_shard.py assumes a plain file.
"""

from __future__ import annotations

import gzip
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator


def resolve(path: Path) -> Path:
    """The file that actually exists: the plain one, else its .gz sibling."""
    if path.is_file():
        return path
    packed = path.parent / (path.name + ".gz")
    return packed if packed.is_file() else path


@contextmanager
def open_jsonl(path: Path) -> Iterator[IO[str]]:
    target = resolve(path)
    if target.suffix == ".gz":
        handle: IO[str] = gzip.open(target, "rt", encoding="utf-8")
    else:
        handle = target.open(encoding="utf-8")
    try:
        yield handle
    finally:
        handle.close()


def exists(path: Path) -> bool:
    return resolve(path).is_file()


def compress_results(path: Path) -> int:
    """Gzip a finished results file in place; returns the bytes reclaimed.

    Atomic: writes to a .tmp, renames, and only then unlinks the original, so a
    crash mid-compression can never lose the timelines.
    """
    if not path.is_file():
        return 0
    packed = path.parent / (path.name + ".gz")
    if packed.is_file():                       # already archived by another run
        path.unlink()
        return 0
    tmp = path.parent / f"{path.name}.{os.getpid()}.tmp"
    before = path.stat().st_size
    try:
        with path.open("rb") as src, gzip.open(tmp, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst, length=8 << 20)
        tmp.replace(packed)
    finally:
        tmp.unlink(missing_ok=True)            # never leave a half-written .tmp
    path.unlink()
    return before - packed.stat().st_size
