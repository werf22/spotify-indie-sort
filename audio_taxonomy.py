"""Controlled audio-tagging vocabulary.

Raw provider labels are never discarded. These labels form an additional,
searchable ontology designed around DJ discovery and the user's library.
"""

BROAD_GENRES = [
    "ambient", "blues", "classical", "country", "dance", "electronic",
    "experimental", "folk", "funk", "hip hop", "indie", "jazz", "latin",
    "metal", "new age", "pop", "punk", "r&b", "reggae", "rock", "soul",
    "soundtrack", "spoken word", "traditional", "world music",
]

SUBGENRES = [
    # House and adjacent club music
    "afro house", "afro tech", "3-step", "amapiano", "ancestral house",
    "organic house", "downtempo house", "deep house", "melodic house",
    "progressive house", "tech house", "tribal house", "latin house",
    "soulful house", "spiritual house", "minimal house", "microhouse",
    "acid house", "classic house", "Chicago house", "French house",
    "disco house", "funky house", "electro house", "future house",
    "bass house", "tropical house", "lo-fi house", "indie dance",
    "dark disco", "nu-disco", "Italo disco", "Balearic beat",
    # Techno, trance and psychedelic music
    "melodic techno", "deep techno", "hypnotic techno", "minimal techno",
    "dub techno", "ambient techno", "acid techno", "Detroit techno",
    "industrial techno", "hard techno", "tribal techno", "psytechno",
    "progressive trance", "psytrance", "goa trance", "dark psytrance",
    "forest psytrance", "organic trance", "deep trance", "tech trance",
    "uplifting trance", "downtempo psy", "psybient", "psychill",
    # Broken rhythms and bass music
    "broken beat", "breakbeat", "progressive breaks", "nu skool breaks",
    "electro", "UK garage", "2-step garage", "future garage",
    "speed garage", "bassline", "UK bass", "dubstep", "deep dubstep",
    "post-dubstep", "drum and bass", "liquid drum and bass", "jungle",
    "halftime", "footwork", "juke", "IDM", "glitch", "glitch hop",
    "wonky", "trip hop", "drill", "grime", "boom bap", "trap",
    # Downtempo, ambient and ritual/organic music
    "ambient", "dark ambient", "drone", "soundscape", "field recording",
    "new age", "meditation music", "healing music", "sound bath",
    "ritual music", "ceremonial music", "shamanic music", "medicine music",
    "ecstatic dance", "conscious dance", "tribal downtempo",
    "organic downtempo", "ethnic electronica", "folktronica",
    "world electronica", "desert blues", "desert electronica",
    "Arabic electronica", "Middle Eastern electronica", "Indian electronica",
    "African electronica", "Latin electronica", "cumbia electronica",
    "digital cumbia", "dub", "ambient dub", "chillout", "lounge",
    # Indie, rock, folk and pop
    "indie rock", "indie pop", "indie folk", "indie electronic",
    "alternative rock", "art rock", "post-rock", "post-punk", "new wave",
    "dream pop", "shoegaze", "slowcore", "psychedelic rock",
    "psychedelic folk", "psychedelic pop", "folk rock", "singer-songwriter",
    "chamber pop", "baroque pop", "synthpop", "electropop", "art pop",
    "bedroom pop", "darkwave", "coldwave", "ethereal wave", "gothic rock",
    "krautrock", "math rock", "noise rock", "grunge", "soft rock",
    "progressive rock", "classic rock", "pop rock", "alternative pop",
    # Acoustic, orchestral, jazz and global traditions
    "contemporary classical", "modern classical", "neoclassical",
    "minimalism", "solo piano", "orchestral", "cinematic", "film score",
    "jazz fusion", "spiritual jazz", "nu jazz", "acid jazz", "ambient jazz",
    "Afrobeat", "Afrobeats", "highlife", "gqom", "kuduro", "soukous",
    "gnawa", "raï", "flamenco", "bossa nova", "samba", "cumbia",
    "salsa", "reggaeton", "dancehall", "roots reggae", "neo soul",
    "alternative r&b", "funk", "disco", "gospel", "mantra", "devotional",
]

MOODS = [
    # Core affect
    "happy", "joyful", "playful", "cheerful", "optimistic", "hopeful",
    "uplifting", "euphoric", "ecstatic", "celebratory", "triumphant",
    "sad", "melancholic", "wistful", "bittersweet", "somber", "grieving",
    "lonely", "heartbroken", "nostalgic", "sentimental", "yearning",
    "angry", "aggressive", "rebellious", "tense", "anxious", "restless",
    "ominous", "threatening", "sinister", "scary", "unsettling",
    # Calm, intimacy and contemplation
    "calm", "peaceful", "serene", "relaxed", "soothing", "gentle",
    "tender", "intimate", "romantic", "sensual", "warm", "comforting",
    "reflective", "contemplative", "introspective", "meditative",
    "mindful", "healing", "grounding", "centered", "spacious",
    # Atmosphere and imagery
    "dreamy", "ethereal", "otherworldly", "mystical", "magical",
    "spiritual", "sacred", "ritualistic", "shamanic", "transcendent",
    "visionary", "psychedelic", "hypnotic", "trance-inducing", "cosmic",
    "celestial", "earthy", "organic", "primal", "tribal", "nature-inspired",
    "watery", "desert-like", "tropical", "nocturnal", "sunrise", "sunset",
    "dark", "mysterious", "haunting", "eerie", "moody", "atmospheric",
    "cinematic", "dramatic", "epic", "majestic", "heroic", "adventurous",
    "futuristic", "mechanical", "industrial", "urban", "raw", "gritty",
    "minimal", "delicate", "fragile", "lush", "rich", "colorful",
    # Energy, motion and DJ function
    "energetic", "powerful", "driving", "propulsive", "pulsing", "groovy",
    "bouncy", "funky", "danceable", "party", "festival", "peak-time",
    "building", "rising", "explosive", "urgent", "fast-paced", "wild",
    "slow", "floating", "weightless", "flowing", "rolling", "swirling",
    "stomping", "marching", "syncopated", "off-kilter", "broken",
    "steady", "repetitive", "entrancing", "releasing", "cathartic",
    # Character and social feeling
    "soulful", "passionate", "emotional", "poetic", "beautiful",
    "inspiring", "empowering", "confident", "cool", "carefree",
    "innocent", "childlike", "quirky", "humorous", "sexy", "seductive",
    "communal", "unifying", "ceremonial", "devotional", "prayerful",
]

INSTRUMENTS = [
    "acoustic guitar", "electric guitar", "bass guitar", "synth bass",
    "piano", "electric piano", "Rhodes piano", "organ", "synthesizer",
    "synth pad", "strings", "violin", "cello", "orchestra", "brass",
    "trumpet", "saxophone", "flute", "clarinet", "harp", "accordion",
    "drums", "drum machine", "kick drum", "snare drum", "hand percussion",
    "congas", "bongos", "djembe", "shaker", "tabla", "frame drum",
    "bells", "singing bowls", "gongs", "field recordings", "nature sounds",
]

VOICE_TAGS = [
    "instrumental", "lead vocals", "male vocals", "female vocals",
    "androgynous vocals", "spoken word", "rap vocals", "choir",
    "group vocals", "chanting", "mantra vocals", "ethereal vocals",
    "soulful vocals", "processed vocals", "vocal chops", "wordless vocals",
]
