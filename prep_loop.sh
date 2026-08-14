#!/bin/bash
# Overnight clip factory.
#
# WHY THIS EXISTS: the daemon's audio-prep job hangs with its worker threads idle
# and no ffmpeg running — 19 minutes alive for 12 s of CPU — while the identical
# command at a smaller --limit completes reliably (40 clips in 27 s, 300 in 188 s).
# Rather than let the night produce nothing while that is root-caused, this runs
# the PROVEN small-batch form in a loop, and a batch that wedges is killed and
# retried instead of stalling the queue forever.
#
# HOW TO TWEAK: BATCH is the proven-good pass size; HARD_TIMEOUT must exceed a
# healthy batch (188 s measured for 300) with margin, but stay short enough that
# a wedged pass costs minutes, not hours.
cd "/Users/jakub/Appky Claude/spotify-indie-sort"
BATCH=300
HARD_TIMEOUT=600
while true; do
  # Report the external disk's state each cycle so a stall is never a mystery.
  # Work does NOT wait for it: prep skips absent sources, so local tracks keep
  # flowing while T7 is unplugged, and T7's own tracks resume by themselves the
  # moment it reappears — no restart, no intervention.
  if [ -d /Volumes/T7 ]; then
    echo "$(date -u +%FT%TZ) T7 present" >> data/prep_loop.log
  else
    echo "$(date -u +%FT%TZ) T7 ABSENT — working local tracks only, will resume T7 on reconnect" >> data/prep_loop.log
  fi
  before=$(ls data/cloud_full/clips/*.opus 2>/dev/null | wc -l | tr -d ' ')
  ./.audio-venv/bin/python prepare_cloud_audio_pilot.py --limit $BATCH --codec opus \
      --workers 6 --full-track --output data/cloud_full >> data/prep_loop.log 2>&1 &
  pid=$!
  waited=0
  while kill -0 $pid 2>/dev/null && [ $waited -lt $HARD_TIMEOUT ]; do sleep 10; waited=$((waited+10)); done
  if kill -0 $pid 2>/dev/null; then
    kill -9 $pid 2>/dev/null
    echo "$(date -u +%FT%TZ) batch wedged after ${HARD_TIMEOUT}s; killed and retrying" >> data/prep_loop.log
  fi
  after=$(ls data/cloud_full/clips/*.opus 2>/dev/null | wc -l | tr -d ' ')
  echo "$(date -u +%FT%TZ) batch done: clips $before -> $after" >> data/prep_loop.log
  sleep 5
done
