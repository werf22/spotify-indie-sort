#!/usr/bin/env python3
"""Plain-language help for every signal the similarity app can compare.

WHY THIS FILE: the app offers 77 switches. Knowing what `onset_rate` or
`audio_style_candidate` measures — and which values are worth typing into a
target box — is the difference between using the tool and guessing with it.
The `ⓘ` button on each row shows what is written here.

WHAT IS HERE AND WHAT IS COMPUTED: only the prose lives here. Coverage, the
real value lists and the real number ranges are read from the database at
request time (see `explain()` in similarity_engine.py), so the help can never
drift away from the data.

HOW TO TWEAK: add or reword an entry below. The key is the signal id without
its prefix — `mood` for `tag:mood`, `energy` for `num:energy` — or the full id
for the embeddings. Anything missing falls back to a description built from the
data itself, so a new signal is never left unexplained.
"""
from __future__ import annotations

# ---------------------------------------------------------------- embeddings
EMBEDDINGS = {
    "CLAP": (
        "Neurónový model trénovaný na dvojiciach zvuk–text: dostával nahrávky "
        "spolu s ich slovným opisom. Naučil sa preto to, čo sa dá o skladbe "
        "povedať slovami — náladu, atmosféru, textúru. Je to jediný z troch, "
        "ktorý naozaj rozumie POCITU.",
        "Zapni, keď chceš ten istý pocit aj v inom žánri. V meraní druhý "
        "najsilnejší signál (MRR 0,43).",
    ),
    "MAEST": (
        "Transformer trénovaný priamo na žánrových a štýlových štítkoch z "
        "Discogs. Nepočuje pocit — počuje ZARADENIE: čo to je za hudbu a do "
        "akej scény patrí.",
        "Zapni, keď chceš zostať v žánri. Vypni, keď chceš zo žánru vyjsť. "
        "MRR 0,39.",
    ),
    "Essentia": (
        "Konvolučná sieť trénovaná na obrovskom katalógu Discogs. Je to "
        "najvšeobecnejšie „ako to znie“ — mix produkcie, zvukovej farby, "
        "nástrojov a hustoty.",
        "Najsilnejší jednotlivý signál v celom systéme (MRR 0,56). Keď nevieš, "
        "čo zapnúť, zapni Essentiu.",
    ),
}

# ---------------------------------------------------------------------- tags
TAGS = {
    "genre": ("Široké zaradenie skladby (electronic, house, pop).",
              "Najlepší jednotlivý tag v meraní (MRR 0,271). Zapni vždy, keď chceš zostať v žánri."),
    "subgenre": ("Jemnejšie delenie pod žánrom.",
                 "Skoro plné pokrytie a solídna sila. Dobrý doplnok ku genre, sám o sebe slabší."),
    "style": ("Najkonkrétnejšie zaradenie z katalógu.",
              "Pozor na pokrytie — chýba skoro polovici knižnice, takže samotné skresľuje výber."),
    "audio_style_candidate": (
        "Štýl odhadnutý priamo zo zvuku modelom MAEST, bez potvrdenia katalógom.",
        "Toto je ten, ktorý funguje na hudbe, o ktorej katalóg nič nevie — biele labely, promá, vlastné edity."),
    "genre_audio_candidate": ("Široký žáner odhadnutý zo zvuku, bez potvrdenia katalógom.",
                              "Používaj v dvojici s audio_style_candidate."),
    "mood": ("Potvrdená nálada skladby.",
             "Chrbtica režimu „Nálada a energia“. Kombinuj s mood_candidate cez makrá."),
    "mood_candidate": (
        "Nálada, ako ju počuje CLAP, bez potvrdenia druhým zdrojom — a je jemnejšia než mood.",
        "Práve tieto slová (building, unifying, uplifting) sú pre stavbu setu užitočnejšie než „happy“."),
    "theme": ("O čom skladba je (club, party, in love, breakup).",
              "Pekné, keď to tam je — a tam je to takmer nikdy. Nechaj s nízkou váhou."),
    "timbre": ("Farba zvuku: tmavý verzus svetlý.",
               "Pre DJ-a mimoriadne užitočné rozlíšenie, ale len na malej časti knižnice."),
    "instrument": ("Potvrdené nástroje v skladbe.",
                   "Dobré na udržanie inštrumentácie (klavír, gitara, dychy) naprieč žánrom."),
    "instrument_candidate": ("Nástroje odhadnuté z CLAP, na celej knižnici, s nižšou istotou.",
                             "Zapni namiesto instrument, keď potrebuješ pokrytie viac než istotu."),
    "voice": ("Je v skladbe spev, alebo je inštrumentálna.",
              "Zapni, keď staviaš inštrumentálnu pasáž a nechceš, aby ti do nej vpadol vokál."),
    "voice_candidate": ("To isté odhadnuté z CLAP, na celej knižnici.",
                        "Širšie pokrytie, nižšia istota."),
    "vocal_character": ("Aký ten hlas je, nie len či tam je.",
                        "Užitočné, keď ti ide o konkrétnu farbu vokálu."),
    "rhythm": ("Typ groovu: four-on-the-floor, broken-beat, mixed-rhythm, beatless.",
               "Plné pokrytie z našej vlastnej analýzy. Pre mix jeden z najpraktickejších tagov vôbec."),
    "production_style": ("Elektronická verzus akustická produkcia.",
                         "Hrubé, ale spoľahlivé — drží ťa na jednej strane tejto hranice."),
    "acoustic_character": ("Akustické verzus elektricky produkované.",
                           "Príbuzné production_style, jemnejšie vo vzťahu k zvuku samotnému."),
    "harmonic_mode": ("Dur alebo mol.", "Ako pravidlo užitočné, na zoradenie nie."),
    "tonality": ("Tonálny charakter skladby.", "Nízke pokrytie — používaj ako pravidlo."),
    "tempo_band": ("Tempové pásmo: club tempo, fast, midtempo, slow.",
                   "Ako pravidlo („musí byť club tempo“) výborné, na zoradenie bezcenné."),
    "energy_level": ("Úroveň energie v troch stupňoch.",
                     "Tri hodnoty znamenajú, že tretina knižnice zdieľa tú istú — preto pravidlo, nie skóre."),
    "energy_band": ("To isté od iného poskytovateľa.",
                    "Zapínať aj energy_level aj energy_band je zdvojenie tej istej váhy."),
    "danceability_level": ("Nakoľko je skladba tanečná, v stupňoch.", "Pravidlo, nie skóre."),
    "danceability_band": ("To isté od iného poskytovateľa.", "Nezapínaj obe naraz."),
    "valence_level": ("Hudobná pozitívnosť v stupňoch.", "Pravidlo, nie skóre."),
    "valence_band": ("To isté od iného poskytovateľa.", "Nezapínaj obe naraz."),
    "label": ("Vydavateľstvo, ktoré skladbu vydalo.",
              "PASCA: najvyšší recall zo všetkých tagov (81 %), ale neidentifikuje zvuk — len to, "
              "že veci vyšli u tej istej firmy. Zapni vedome a len keď prehľadávaš katalóg."),
    "country": ("Krajina vydania.", "Katalógový údaj s nízkym pokrytím."),
    "format": ("Formát vydania (vinyl, digital…).", "Katalógový údaj, so zvukom nesúvisí."),
    "version": ("Označenie verzie (radio edit, extended, remix…).",
                "Užitočné, keď hľadáš konkrétny typ verzie."),
    "remixer": ("Kto skladbu remixoval.", "Zapni, keď hľadáš všetky remixy jedného človeka."),
    "onetagger": ("Štítky z OneTagger / Discogs v2.", "Nízke pokrytie."),
    "production": ("Produkčné poznámky z katalógu.", "Nízke pokrytie."),
    "recording_type": ("Typ nahrávky (štúdio, live…).", "Takmer prázdne."),
    "genre_rosamerica": ("Starý Essentia klasifikátor žánru.",
                         "MŔTVE — prežilo len pri 32 trackoch z prvého testovacieho behu. Nechaj vypnuté."),
    "mood_aggressive": ("Starý binárny Essentia klasifikátor.", "MŔTVE — 32 trackov."),
    "mood_happy": ("Starý binárny Essentia klasifikátor.", "MŔTVE — 32 trackov."),
    "mood_relaxed": ("Starý binárny Essentia klasifikátor.", "MŔTVE — 32 trackov."),
    "mood_sad": ("Starý binárny Essentia klasifikátor.", "MŔTVE — 32 trackov."),
    "voice_instrumental": ("Starý binárny Essentia klasifikátor.", "MŔTVE — 32 trackov."),
}

# ------------------------------------------------------------------- numbers
NUMBERS = {
    "energy": ("Intenzita a nabudenie skladby, 0 až 1.",
               "Toto je to číslo, ktoré chceš mať v režime cieľovej hodnoty, keď staviaš krivku setu. "
               "Skús „> 0,8“ na vrchol alebo „< 0,3“ na intro."),
    "valence": ("Hudobná pozitívnosť, 0 až 1: temné verzus veselé.",
                "Spolu s energy ti dá štyri kvadranty nálady. „> 0,7“ = svetlé, „< 0,3“ = temné."),
    "danceability": ("Nakoľko je skladba tanečná podľa stability rytmu a sily beatu, 0 až 1.",
                     "Na parket chceš vysoké hodnoty."),
    "acousticness": ("Nakoľko akusticky skladba pôsobí, 0 až 1.",
                     "Nízke = elektronická produkcia. „< 0,2“ drží set elektronický."),
    "instrumentalness": ("Nakoľko je skladba bez vokálu, 0 až 1.",
                         "Najpraktickejšie z tejto štvorice. „> 0,7“ = prakticky inštrumentálka."),
    "speechiness": ("Podiel hovoreného slova, 0 až 1.",
                    "Vysoké hodnoty znamenajú rap alebo hovorené intro."),
    "liveness": ("Nakoľko nahrávka pôsobí ako živá, 0 až 1.",
                 "Vysoké hodnoty často znamenajú potlesk alebo priestor sály."),
    "loudness": ("Hlasitosť masteringu (normalizovaná).",
                 "Nie hlasitosť prehrávania — ide o to, ako agresívne je vec zmastrovaná."),
    "loudness_db": ("Hlasitosť masteringu v decibeloch, typicky −20 až 0.",
                    "Užitočné, aby ti nasledujúci track nespadol o 6 dB."),
    "onset_rate": ("Hustota nástupov tónov za sekundu — koľko sa toho deje.",
                   "V meraní jedno z najsilnejších čísel (MRR 0,344), ALE existuje len na 13 % knižnice."),
    "average_loudness": ("Priemerná hlasitosť z Essentie.",
                         "Silné (0,334), ale len na 13 % knižnice."),
    "dynamic_complexity": ("Dynamický rozsah — rozdiel medzi tichom a vrcholom.",
                           "Silné (0,292), ale len na 13 % knižnice. Nízke = zmastrované nahlas a ploché."),
    "four_on_floor_score": ("Nakoľko je to rovný kop na štyri doby, 0 až 1.",
                            "Prakticky najdôležitejšie číslo pre mixovanie — rozdiel medzi housom a breakbeatom je presne tu."),
    "broken_beat_score": ("Nakoľko je rytmus lámaný, 0 až 1.",
                          "Opak four_on_floor. Drum'n'bass, jungle, UK garage."),
    "syncopation_score": ("Koľko je v groove synkopy — dôrazov mimo hlavné doby.",
                          "Vysoká hodnota znamená groove, ktorý „tlačí“."),
    "rhythm_regularity": ("Nakoľko je rytmický vzor pravidelný počas celej skladby.",
                          "Nízka hodnota = skladba sa rytmicky vyvíja alebo je hraná naživo."),
    "tempo_stability": ("Drží skladba tempo, alebo pláva?",
                        "Nízka hodnota u živých nahrávok a vecí bez klikáča. Pri mixovaní je to varovanie."),
    "beat_presence_score": ("Nakoľko je vôbec počuť beat.",
                            "Blízko nuly znamená ambient alebo intro."),
    "beat_section_coverage": ("Aká časť skladby má rozpoznateľný beat.",
                              "Nízke = dlhé beatless pasáže."),
    "rhythm_pattern_coverage": ("Aká časť skladby sedí na rozpoznaný rytmický vzor.", ""),
    "kick_on_quarter_ratio": ("Podiel kopákov presne na štvrťových dobách.",
                              "Zaujímavé, ale existuje len na 684 trackoch."),
    "offbeat_kick_ratio": ("Podiel kopákov mimo hlavné doby.", "Len 684 trackov."),
    "duration_ms": ("Dĺžka skladby v milisekundách.",
                    "So zvukom nesúvisí. Užitočné nanajvýš ako filter na dĺžku."),
    "mode": ("Dur (1) alebo mol (0).", "Ako pravidlo, nie ako skóre."),
    "time_signature": ("Taktové označenie, takmer vždy 4.", "Prakticky konštanta."),
    "is_remix": ("Či je nahrávka remix (1) alebo nie (0).",
                 "Ako filter: „= 1“ vyhodí len remixy."),
    "bpm": ("POZOR: tempo od INÉHO poskytovateľa než to, ktoré vidíš v tabuľke — "
            "nezhodujú sa pri 65 % knižnice.",
            "Cieľ na tempo nastavuj na BPM v sekcii Hudobné, nie tu."),
    "tempo": ("To isté ako bpm, iný zdroj.", "Nepoužívaj na cielenie tempa."),
    "track.bpm": ("Tempo tak, ako ho udáva Spotify.", "Opäť iný zdroj než tabuľka."),
    "key": ("Tónina ako číslo od iného zdroja.", "Na cielenie tóniny použi prepínač Mixed in Key."),
    "key_int": ("Tónina ako celé číslo, iný zdroj.", "To isté."),
    "track.duration": ("Dĺžka skladby podľa Spotify.", "So zvukom nesúvisí."),
}

# ------------------------------------------------------------------- musical
MUSICAL = {
    "bpm": ("Tempo skladby — to isté číslo, aké je v tabuľke.",
            "Na zoradenie je tempo takmer bezcenné (MRR 0,001), lebo tisíce trackov ho zdieľajú. "
            "Jeho sila je vo filtrovaní: nastav cieľ („→ 174, ± 4“) alebo použi prepínač BPM ± hore."),
    "key": ("Tónina skladby v Camelot systéme.",
            "Rovnako ako tempo: na zoradenie takmer nanič (MRR 0,002), ako sito výborné. "
            "Používaj cez prepínač Mixed in Key alebo cez políčka Harmonicky."),
}


def prose(group: str, key: str) -> tuple[str, str]:
    """(what it is, how to use it) — empty strings when nothing is written."""
    table = {"audio": EMBEDDINGS, "tags": TAGS, "numbers": NUMBERS, "musical": MUSICAL}
    return table.get(group, {}).get(key, ("", ""))
