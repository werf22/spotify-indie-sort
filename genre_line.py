"""
The taste calibration for this whole tool, in one place so it's easy to tweak.
Edit KEEP_EXAMPLES or the boundary description below to shift what counts as
"Indie" — everything else (export.py, classify.py) just imports this.
"""

# Confirmed 2026-07-13 with the owner, calibrated against 8 reference tracks.
BOUNDARY_DESCRIPTION = """
EXCLUDE: functional dancefloor / ceremonial groove music — afro house, organic
house, shamanic house, ecstatic-dance journeys, tribal/world-percussion
instrumentals. This is music built for a DJ set or a movement/dance ritual:
long, repetitive, groove-first, usually no traditional song structure.

KEEP: song-form or melodic listening music — indie rock/folk/pop, alternative,
dream pop, trip-hop, ambient/downtempo, IDM, singer-songwriter, and yes
melodic/indie techno. The test is the TRACK, not the artist or scene: an
artist who's big in the conscious/ecstatic-dance world (e.g. RY X) still
counts as KEEP when the specific track is a verse-structured song rather than
an instrumental groove.

When genuinely unsure, lean KEEP — this playlist is meant to catch "normal"
listening music, not to be a strict genre filter.
""".strip()

# (artist, title) — the owner's own reference points for "this is Indie".
KEEP_EXAMPLES = [
    ("Daughter", "Youth"),
    ("RY X", "Berlin"),
    ("Nuages", "Dreams"),
    ("The Flashbulb", "I Can Feel It Humming"),
    ("Cameron Hayes", "Spend The Night"),
    ("alt-J", "Taro"),
    ("Massive Attack feat. Elizabeth Fraser", "Teardrop"),
    ("Beirut", "Nantes"),
]
