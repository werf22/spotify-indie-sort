#!/usr/bin/env python3
"""The one-click filters — moods, energy, rhythm and genres.

WHY THIS FILE EXISTS SEPARATELY: the lists are long, they are curated by hand
against the real vocabulary, and they change far more often than the engine
does. Keeping them here means the engine never grows another two hundred lines
of data.

STRICT BY CONSTRUCTION. Every value below is an EXACT tag value that exists in
the library — matching is exact, never substring. That is deliberate and it is
the whole point of the rewrite: substring matching quietly did both halves of
the wrong thing. It MISSED (a macro asking for "drum n bass" never found the
1,206 tracks tagged plain `dnb`, nor `drum & bass`, nor `jungle/drum'n'bass`)
and it OVER-MATCHED (the disco/funk macro pulled in `liquid funk`, which is
drum'n'bass, because "funk" is a substring of it).

HOW TO TWEAK: add or remove values from a list. To find out what really exists:

    SELECT tag, COUNT(DISTINCT spotify_id) c FROM tags
    WHERE tag_type IN ('genre','subgenre','style')
    GROUP BY tag HAVING c >= 150 ORDER BY c DESC;

Slovak spellings (`elektronická`, `tanečná`, `klasická`, `džez`) are included
on purpose: Deezer localised some tags before that was stopped, and those
tracks would otherwise be invisible to these filters. See LESSONS.md.
"""
from __future__ import annotations

# How sure a tag must be before a macro counts it. A track carries a median of
# 26 genre tags from a dozen sources and most are artist-level guesses at 0.15,
# so without this a genre filter matched nearly everything electronic. Measured
# at 0.8 the macros sharpen objectively — see the note in tag_rule_mask.
# TWEAK: lower it to catch more and mean less; raise it to be stricter still.
# PER GROUP, because the scales are not the same. Genre tags come from a dozen
# sources and are dominated by artist-level guesses at 0.15, so 0.8 is what
# separates a real genre from noise. Mood and rhythm come from our own analysis
# and sit mostly at 0.6-0.7 — applying 0.8 there wiped "Temné" from 19,122
# tracks down to 68. Energy, danceability and valence are emitted at a flat 0.8,
# so anything above that would empty them.
MACRO_MIN_CONF = 0.8                 # fallback for anything unlisted
GROUP_MIN_CONF = {
    "Žáner": 0.8,
    "Nálada": 0.5,   # measured: 0.6 collapses Temné 19,089 -> 1,233 and Chill 1,655 -> 85
    "Rytmus a tempo": 0.6,
    "Energia": 0.5,
}

GENRE_TYPES = "genre|subgenre|style"
MOOD_TYPES = "mood|mood_candidate"


def _v(*values: str) -> str:
    return "|".join(values)


MACROS: list[dict] = [
    {"group": "Nálada", "items": [
        # `mood` ALONE for anything whose word floods `mood_candidate`. Those
        # candidates are guesses spread across the whole library — happy sits on
        # 61k tracks there, unifying on 58k — so including them turned "Veselé"
        # into a filter that matched 99.5 % of everything.
        {"id": "m_happy", "label": "Veselé", "type": "mood",
         "value": _v("happy", "joyful", "cheerful", "good natured", "positive")},
        {"id": "m_play", "label": "Hravé", "type": "mood",
         "value": _v("funny", "quirky", "playful", "carefree", "humorous", "fun")},
        {"id": "m_uplift", "label": "Euforické", "type": "mood",
         "value": _v("euphoric", "uplifting", "blissful", "transcendent", "rousing")},
        {"id": "m_hope", "label": "Nádej", "type": MOOD_TYPES,
         "value": _v("hopeful", "optimistic", "triumphant", "empowering", "enlightened")},
        {"id": "m_motiv", "label": "Motivačné", "type": "mood",
         "value": _v("motivational", "inspiring", "powerful")},
        {"id": "m_energ", "label": "Energické", "type": "mood",
         "value": _v("energetic", "excitable", "boisterous")},
        {"id": "m_drive", "label": "Ženúce dopredu", "type": MOOD_TYPES,
         "value": _v("propulsive", "upbeat", "driving", "pulsing", "rolling", "stomping")},
        {"id": "m_party", "label": "Párty", "type": "mood", "value": _v("party")},
        {"id": "m_sexy", "label": "Sexy / zmyselné", "type": MOOD_TYPES,
         "value": _v("sensual", "sexy", "passionate", "smooth", "sophisticated")},
        {"id": "m_love", "label": "Romantické", "type": "mood",
         "value": _v("love", "in love", "romantic")},
        {"id": "m_tender", "label": "Nežné", "type": MOOD_TYPES,
         "value": _v("tender", "gentle", "soft", "warm", "innocent", "soothing")},
        {"id": "m_summer", "label": "Letné", "type": "mood",
         "value": _v("summer", "sunny", "sunrise")},
        {"id": "m_chill", "label": "Chill", "type": MOOD_TYPES,
         "value": _v("chill", "chilled", "mellow", "cool")},
        {"id": "m_relax", "label": "Uvoľnené", "type": "mood",
         "value": _v("relaxed", "relaxing")},
        {"id": "m_peace", "label": "Mierumilovné", "type": "mood",
         "value": _v("peaceful", "serene", "calm")},
        {"id": "m_medit", "label": "Meditatívne", "type": MOOD_TYPES,
         "value": _v("meditative", "mindful", "spiritual", "ritual", "ritualistic", "sacred")},
        {"id": "m_deep", "label": "Hlboké", "type": "mood", "value": _v("deep")},
        {"id": "m_dreamy", "label": "Snové", "type": MOOD_TYPES,
         "value": _v("dreamy", "dream", "ethereal", "celestial")},
        {"id": "m_cosmic", "label": "Kozmické", "type": MOOD_TYPES,
         "value": _v("space", "cosmic", "soundscape", "atmospheric", "nocturnal")},
        {"id": "m_hypno", "label": "Hypnotické", "type": MOOD_TYPES,
         "value": _v("hypnotic", "trippy")},
        {"id": "m_psy", "label": "Psychedelické", "type": MOOD_TYPES,
         "value": _v("psychedelic", "mystical", "weird", "primal")},
        {"id": "m_melan", "label": "Melancholické", "type": "mood",
         "value": _v("melancholic", "melancholy", "wistful", "bittersweet", "moody")},
        {"id": "m_sad", "label": "Smutné", "type": "mood",
         "value": _v("sad", "poignant", "troubled", "somber")},
        {"id": "m_somber", "label": "Zádumčivé", "type": "mood",
         "value": _v("contemplative", "reflective", "philosophical")},
        {"id": "m_dark", "label": "Temné", "type": "mood",
         "value": _v("dark", "creepy", "haunting", "scary")},
        {"id": "m_tense", "label": "Napäté", "type": MOOD_TYPES,
         "value": _v("tense", "anxious", "unsettling", "urgent", "threatening")},
        {"id": "m_aggro", "label": "Agresívne", "type": "mood",
         "value": _v("aggressive", "angry", "confrontational", "gritty")},
        {"id": "m_heavy", "label": "Ťaživé", "type": MOOD_TYPES,
         "value": _v("heavy", "intense", "primal", "industrial")},
        {"id": "m_epic", "label": "Dramatické / epické", "type": "mood",
         "value": _v("epic", "dramatic", "drama", "trailer")},
        {"id": "m_cinema", "label": "Kinematické", "type": "mood",
         "value": _v("cinematic", "film", "movie", "documentary")},
        {"id": "m_action", "label": "Akčné / športové", "type": MOOD_TYPES,
         "value": _v("action", "sport", "adventure", "adventurous", "game")},
        {"id": "m_emo", "label": "Emotívne", "type": MOOD_TYPES,
         "value": _v("emotional", "cathartic", "beautiful", "poetic")},
        {"id": "m_retro", "label": "Retro / nostalgické", "type": "mood",
         "value": _v("retro", "nostalgic")},
        {"id": "m_neutral", "label": "Neutrálne / podkres", "type": "mood",
         "value": _v("neutral", "background", "corporate", "advertising")},
        {"id": "m_xmas", "label": "Vianočné", "type": MOOD_TYPES,
         "value": _v("christmas", "holiday")},
        {"id": "m_tbright", "label": "Svetlý zvuk", "type": "timbre", "value": "bright"},
        {"id": "m_tdark", "label": "Tmavý zvuk", "type": "timbre", "value": "dark"},
    ]},

    {"group": "Energia", "items": [
        {"id": "e_high", "label": "Vysoká energia", "type": "energy_level|energy_band",
         "value": _v("high-energy", "high")},
        {"id": "e_mid", "label": "Stredná energia", "type": "energy_level|energy_band",
         "value": _v("mid-energy", "medium")},
        {"id": "e_low", "label": "Nízka energia", "type": "energy_level|energy_band",
         "value": _v("low-energy", "low")},
        {"id": "e_dance", "label": "Veľmi tanečné", "type": "danceability_level",
         "value": "very-danceable"},
        {"id": "e_nodance", "label": "Netanečné", "type": "danceability_level",
         "value": "not-danceable"},
        {"id": "e_pos", "label": "Pozitívne", "type": "valence_level", "value": "uplifting"},
        {"id": "e_neg", "label": "Ťažké", "type": "valence_level", "value": "melancholic"},
    ]},

    {"group": "Rytmus a tempo", "items": [
        {"id": "r_four", "label": "Rovný kop", "type": "rhythm", "value": "four-on-the-floor"},
        {"id": "r_broken", "label": "Broken beat", "type": "rhythm", "value": "broken-beat"},
        {"id": "r_mixed", "label": "Zmiešaný rytmus", "type": "rhythm", "value": "mixed-rhythm"},
        {"id": "r_beatless", "label": "Bez beatu", "type": "rhythm", "value": "beatless"},
        {"id": "r_club", "label": "Klubové tempo", "type": "tempo_band", "value": "club tempo"},
        {"id": "r_fast", "label": "Rýchle", "type": "tempo_band", "value": "fast"},
        {"id": "r_mid", "label": "Midtempo", "type": "tempo_band", "value": "midtempo"},
        {"id": "r_slow", "label": "Pomalé", "type": "tempo_band", "value": "slow"},
    ]},

    # ---- genres: every value below was read out of the library ----------
    {"group": "Žáner", "items": [
        {"id": "g_house", "label": "House (všetko)", "type": GENRE_TYPES,
         "value": _v("house", "deep house", "tech house", "tech-house", "techhouse",
                     "afro house", "tribal house", "organic house", "melodic house",
                     "progressive house", "latin house", "disco house", "funky house",
                     "future house", "bass house", "chill house", "garage house",
                     "g-house", "slap house", "jazz house", "hip house", "lo-fi house",
                     "microhouse", "minimal deep house", "french house", "euro house",
                     "stutter house", "bongo house", "rally house", "vocal house",
                     "acid house", "electro house", "tropical house", "deep tech",
                     "techno/house")},
        {"id": "g_deep", "label": "Deep house", "type": GENRE_TYPES,
         "value": _v("deep house", "minimal deep house", "deep tech", "deep techno")},
        {"id": "g_tech", "label": "Tech house", "type": GENRE_TYPES,
         "value": _v("tech house", "tech-house", "techhouse")},
        {"id": "g_techno", "label": "Techno", "type": GENRE_TYPES,
         "value": _v("techno", "minimal techno", "melodic techno", "techno/house",
                     "deep techno", "acid techno", "ambient techno", "dub techno",
                     "minimal-techno", "minimal", "hard techno")},
        {"id": "g_melodic", "label": "Melodic / progressive", "type": GENRE_TYPES,
         "value": _v("melodic house", "melodic techno", "progressive house",
                     "progressive", "progressive trance", "indie dance")},
        {"id": "g_afro", "label": "Afro / amapiano", "type": GENRE_TYPES,
         "value": _v("afro house", "afro tech", "afropiano", "amapiano", "gqom",
                     "afrobeat", "afrobeats", "afropop", "afro-pop", "afro soul",
                     "afro r&b", "afroswing", "afro eletronic", "tribal house",
                     "tribal", "kuduro", "azonto", "bongo house", "bongo piano",
                     "private school piano", "ndombolo", "highlife", "hiplife",
                     "african", "africká hudba", "south african", "gnawa")},
        {"id": "g_organic", "label": "Organic / downtempo", "type": GENRE_TYPES,
         "value": _v("organic house", "downtempo", "downbeat", "chillout",
                     "chill out/trip-hop/lounge", "lounge", "chillwave", "trip-hop",
                     "trip hop", "psychill", "psybient", "folktronica")},
        {"id": "g_dnb", "label": "Drum'n'bass", "type": GENRE_TYPES,
         "value": _v("drum and bass", "drum n bass", "drum & bass", "drum'n'bass",
                     "dnb", "jungle", "jungle/drum'n'bass", "ragga jungle",
                     # breakcore (median 120 BPM, 11 % in dnb tempo) and
                     # halftime (88 BPM) measured as impostors here — breakcore
                     # sits with the breakbeats instead.
                     "liquid funk", "neurofunk", "drumstep", "drill n bass",
                     "techstep", "jump up")},
        {"id": "g_garage", "label": "UK garage / 2-step", "type": GENRE_TYPES,
         "value": _v("uk garage", "garage", "speed garage", "future garage",
                     "2-step", "2step", "2 step", "3 step", "uk funky", "bassline",
                     "uk bass", "bass music")},
        {"id": "g_dubstep", "label": "Dubstep / bass", "type": GENRE_TYPES,
         "value": _v("dubstep", "post-dubstep", "riddim", "chillstep", "future bass",
                     "tropical bass", "brazilian bass", "wonky", "glitch hop",
                     "glitch-hop", "footwork", "juke", "miami bass")},
        {"id": "g_grime", "label": "Grime / drill", "type": GENRE_TYPES,
         "value": _v("grime", "uk grime", "drill", "uk drill")},
        {"id": "g_breaks", "label": "Breakbeat", "type": GENRE_TYPES,
         "value": _v("breakbeat", "breaks", "big beat", "psybreaks",
                     "nu skool breaks", "breakcore")},
        {"id": "g_trance", "label": "Trance", "type": GENRE_TYPES,
         "value": _v("trance", "psytrance", "psy-trance", "progressive trance",
                     "goa trance", "goa", "vocal trance", "uplifting trance",
                     "psychedelic trance", "progressive psytrance", "neotrance", "psy")},
        {"id": "g_ambient", "label": "Ambient", "type": GENRE_TYPES,
         "value": _v("ambient", "dark ambient", "ambient pop", "ambient techno",
                     "new age", "drone", "space music", "meditation", "mantra",
                     "mantras", "kirtans", "kirtana", "bhajans", "minimalism")},
        {"id": "g_electro", "label": "Electro / EDM", "type": GENRE_TYPES,
         "value": _v("electro", "electro house", "edm", "big room", "rave",
                     "electroclash", "moombahton", "hard house", "acid",
                     "eurodance", "europop", "elektro")},
        {"id": "g_disco", "label": "Disco / funk / soul", "type": GENRE_TYPES,
         "value": _v("disco", "nu disco", "nu-disco", "disco house", "post-disco",
                     "funk", "funk / soul", "soul & funk", "soul", "neo-soul",
                     "neo soul", "r&b", "rnb", "r&b/soul", "r-b-soul", "randb",
                     "contemporary r&b", "contemporary rnb", "alternative r&b",
                     "alternative rnb", "uk r&b", "rnb/swing", "funky",
                     "electro swing", "electro-swing", "electroswing", "boogie")},
        {"id": "g_hiphop", "label": "Hip hop / rap / trap", "type": GENRE_TYPES,
         "value": _v("hip hop", "hip-hop", "hiphop", "rap", "rap/hip hop",
                     "hip-hop/rap", "hip-hop-rap", "trap", "trap music", "edm trap",
                     "trap queen", "pop rap", "gangsta rap", "gangsta",
                     "southern hip hop", "southern rap", "underground hip-hop",
                     "underground hip hop", "underground rap", "uk hip hop",
                     "uk hip-hop", "uk rap", "east coast hip hop", "east coast rap",
                     "instrumental hip-hop", "hardcore hip hop", "dirty south",
                     "crunk", "acid crunk", "female rap", "drill", "uk drill",
                     "suomirap", "suomihoppi", "suomi hip-hop", "ghanaian hip hop")},
        {"id": "g_latin", "label": "Latin / brazil", "type": GENRE_TYPES,
         "value": _v("latin", "latino", "latin house", "latin jazz", "latin pop",
                     "salsa", "cumbia", "electrocumbia", "reggaeton", "dembow",
                     "neoperreo", "guaracha", "moombahton", "brazilian funk",
                     "baile funk", "funk carioca", "mpb", "brazilian pop", "brasil",
                     "brazílska hudba", "soca", "shatta", "techengue", "bacardi")},
        {"id": "g_reggae", "label": "Reggae / dub", "type": GENRE_TYPES,
         "value": _v("reggae", "roots reggae", "dancehall", "dancehall/ragga",
                     "modern dancehall", "ragga", "dub", "psydub", "lovers rock",
                     "jamaican", "jamaica", "ska")},
        {"id": "g_pop", "label": "Pop", "type": GENRE_TYPES,
         "value": _v("pop", "electropop", "synthpop", "synth-pop", "synth pop",
                     "dance-pop", "dance pop", "indie pop", "art pop", "alt-pop",
                     "alternative pop", "dream pop", "j-pop", "k-pop", "latin pop",
                     "brazilian pop", "bangla pop", "adult contemporary",
                     "medzinárodný pop", "pop/rock", "pop rock", "funk pop")},
        {"id": "g_rock", "label": "Rock / metal", "type": GENRE_TYPES,
         "value": _v("rock", "indie rock", "alternative rock", "hard rock",
                     "classic rock", "punk", "punk rock", "post-rock", "post-punk",
                     "progressive rock", "psychedelic rock", "soft rock", "folk rock",
                     "blues rock", "art rock", "glam rock", "space rock", "grunge",
                     "shoegaze", "britpop", "emo", "pop punk", "post-hardcore",
                     "metal", "heavy metal", "death metal", "black metal",
                     "doom metal", "doom", "thrash metal", "metalcore",
                     "alternative metal", "progressive metal", "hardcore",
                     "hardcore punk", "sludge", "industrial", "post-industrial",
                     "noise", "krautrock", "new wave", "darkwave", "ebm",
                     "indie rock/rock pop", "alternative", "alternatívna", "indie")},
        {"id": "g_jazz", "label": "Jazz / blues", "type": GENRE_TYPES,
         "value": _v("jazz", "nu jazz", "nu-jazz", "acid jazz", "latin jazz",
                     "jazz house", "vocal jazz", "smooth jazz", "future jazz", "džez",
                     "swing", "swing music", "blues", "blues rock",
                     "rhythm and blues", "fusion", "world fusion")},
        {"id": "g_class", "label": "Klasika / soundtrack", "type": GENRE_TYPES,
         "value": _v("classical", "modern classical", "contemporary classical",
                     "neoclassical", "neo-classical", "post-classical",
                     "classical crossover", "orchestral", "medieval", "klasická",
                     "composer", "composers", "score", "soundtrack",
                     "movie soundtrack", "soundtracks", "stage & screen",
                     "video game music", "vgm", "cinematic", "filmová hudba",
                     "filmy/hry", "piano")},
        {"id": "g_folk", "label": "Folk / world", "type": GENRE_TYPES,
         "value": _v("folk", "indie folk", "folk rock", "folktronica", "neofolk",
                     "electrofolk", "folk fusion", "folk, world, & country", "world",
                     "world music", "world fusion", "ethnic", "celtic", "flamenco",
                     "oriental", "appalachian", "bluegrass", "americana", "country",
                     "gothic country", "singer-songwriter", "singer & songwriter",
                     "singer/songwriter", "acoustic")},
        {"id": "g_exp", "label": "Experimentálne / IDM", "type": GENRE_TYPES,
         "value": _v("experimental", "experimental electronic", "idm", "glitch",
                     "leftfield", "avant-garde", "abstract", "electroacoustic",
                     "sound collage", "deconstructed club", "lo-fi", "electronica")},
    ]},
]
