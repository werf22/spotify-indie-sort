import json, os, sys, time, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
sys.path.insert(0, "/Users/jakub/Appky Claude/spotify-indie-sort")
import pod_reaper as R

tmp = Path(tempfile.mkdtemp())
R.SHARDS = tmp

def make(shard, age_min, results_age_min=None, results_bytes=0):
    d = tmp / shard; d.mkdir(parents=True, exist_ok=True)
    born = datetime.now(timezone.utc) - timedelta(minutes=age_min)
    (d / "runpod_state.json").write_text(json.dumps({"created_at": born.isoformat().replace("+00:00","Z")}))
    if results_age_min is not None:
        f = d / "results.jsonl"; f.write_bytes(b"x" * max(results_bytes,1))
        t = time.time() - results_age_min*60
        os.utime(f, (t, t))
    return {"name": f"music-db-{shard}", "id": "podid"}

cases = [
    ("setup grace, no results yet",      make("shard-0001", 8),                      {"shard-0001"}, True,  "WORKING"),
    ("mid-upload at 40 min (grace 45)",  make("shard-0002", 40, 2, 5_000_000),       {"shard-0002"}, True,  "WORKING"),
    ("past grace, results STALE",        make("shard-0003", 60, 30, 5_000_000),      {"shard-0003"}, True,  "KILL"),
    ("no runner owns the shard",         make("shard-0004", 10, 1, 1_000),           set(),          True,  "KILL"),
    ("no runner but pgrep unknown",      make("shard-0005", 10, 1, 1_000),           set(),          False, "WORKING"),
    ("past the hard time box",           make("shard-0006", 90, 1, 5_000_000),       {"shard-0006"}, True,  "KILL"),
    ("past grace, never any results",    make("shard-0007", 60),                     {"shard-0007"}, True,  "KILL"),
    ("young runner-less pod (race)",     make("shard-0008", 1),                      set(),          True,  "WORKING"),
    # THE REGRESSION: a resumed shard carries a results file from a previous run
    # whose mtime is hours or days old. The pod is brand new and uploading; it
    # must NOT be blamed for time that predates it.
    ("resumed shard, 34h-old results, pod 3 min", make("shard-0009", 3, 2053, 36_000_000), {"shard-0009"}, True, "WORKING"),
    ("resumed shard, old file, pod past grace and idle", make("shard-0010", 60, 2053, 36_000_000), {"shard-0010"}, True, "KILL"),
]
cases.append(("pod with no shard dir", {"name": "music-db-shard-9999", "id": "x"}, set(), True, "KILL"))

fails = 0
for label, pod, runners, known, expect in cases:
    got, reason = R.judge(pod, runners, known)
    ok = got == expect
    fails += (not ok)
    print(f"{'PASS' if ok else 'FAIL'}  {label:34} -> {got:8} ({reason})")
print("\nALL PASS" if not fails else f"\n{fails} FAILURES — do not deploy")
sys.exit(1 if fails else 0)
