"""Fictional demo catalog.

Audio numbers here are editorial metadata written so the demo can run. They are
not measurements of recordings, and the artists are not a licensed library.
`feature_source` is `editorial_demo_not_from_audio` on every row.

Replace this catalog through the CSV ingest path described in docs/DATASET.md.
"""

from __future__ import annotations

import numpy as np

from app.data.catalog import Track, editorial_key, validate_track_vocab

# title, artist, album, genres, language, year, seconds, tempo, energy,
# danceability, acousticness, valence, mood tags
_ROWS: list[tuple] = [
    ("Paper Boats", "Anik Sen", "Riverlight", ("bengali-modern", "indie"), "bn", 2022, 214, 92, 0.30, 0.34, 0.80, 0.24, ("melancholic", "nocturnal")),
    ("Lamp on the Ferry", "Anik Sen", "Riverlight", ("bengali-modern", "indie"), "bn", 2022, 236, 104, 0.40, 0.42, 0.70, 0.55, ("calm", "hopeful")),
    ("Monsoon Static", "Anik Sen", "After Rain", ("bengali-modern", "indie"), "bn", 2024, 221, 88, 0.28, 0.30, 0.84, 0.22, ("melancholic", "dreamy")),
    ("Terrace at Dusk", "Rhea Mukherjee", "City of Balconies", ("indie", "bengali-modern"), "bn", 2023, 208, 98, 0.38, 0.45, 0.62, 0.58, ("romantic", "nocturnal")),
    ("Handwritten", "Rhea Mukherjee", "City of Balconies", ("singer-songwriter", "bengali-modern"), "bn", 2023, 196, 86, 0.26, 0.32, 0.88, 0.36, ("calm", "melancholic")),
    ("Delta Frequencies", "Nodi Echo", "Current", ("electronic", "bengali-modern"), "bn", 2024, 242, 118, 0.55, 0.62, 0.28, 0.48, ("dreamy", "nocturnal")),
    ("Salt Grammar", "Nodi Echo", "Current", ("electronic", "indie"), "bn", 2024, 228, 122, 0.72, 0.74, 0.18, 0.60, ("energetic", "groovy")),
    ("Neel Dupatta", "Meher Kapoor", "Studio 4", ("bollywood", "pop"), "hi", 2021, 231, 108, 0.64, 0.68, 0.34, 0.80, ("joyful", "romantic")),
    ("Quiet Cinema", "Meher Kapoor", "Studio 4", ("bollywood", "singer-songwriter"), "hi", 2021, 219, 90, 0.34, 0.40, 0.66, 0.32, ("melancholic", "romantic")),
    ("Platform 3", "Arjun Vyas", "Night Train", ("indie", "singer-songwriter"), "hi", 2023, 205, 96, 0.36, 0.38, 0.72, 0.40, ("nocturnal", "calm")),
    ("Yellow Window", "Arjun Vyas", "Night Train", ("indie", "pop"), "hi", 2023, 214, 112, 0.58, 0.56, 0.46, 0.74, ("hopeful", "joyful")),
    ("Glass Orchard", "Mira Ellison", "Low Light", ("indie", "singer-songwriter"), "en", 2020, 228, 94, 0.33, 0.36, 0.76, 0.30, ("melancholic", "dreamy")),
    ("Second Coffee", "Mira Ellison", "Low Light", ("indie", "singer-songwriter"), "en", 2020, 201, 102, 0.42, 0.48, 0.64, 0.62, ("calm", "hopeful")),
    ("Kitchen Radio", "Mira Ellison", "Neighbors", ("pop", "indie"), "en", 2023, 196, 116, 0.66, 0.72, 0.30, 0.78, ("joyful", "groovy")),
    ("Hull Down", "North Atlantic", "Charts", ("rock", "alt"), "en", 2019, 248, 132, 0.78, 0.52, 0.12, 0.46, ("energetic", "tense")),
    ("Mariner's Hymn", "North Atlantic", "Charts", ("rock", "folk"), "en", 2019, 264, 120, 0.66, 0.48, 0.22, 0.60, ("hopeful", "energetic")),
    ("Wool Coat", "The Lantern Room", "Winter Porch", ("folk", "indie"), "en", 2018, 214, 84, 0.26, 0.30, 0.88, 0.34, ("calm", "melancholic")),
    ("County Line", "The Lantern Room", "Winter Porch", ("folk", "singer-songwriter"), "en", 2018, 232, 108, 0.48, 0.46, 0.72, 0.66, ("hopeful", "calm")),
    ("Sunglasses Indoors", "June Harbor", "Bright", ("pop",), "en", 2024, 188, 118, 0.76, 0.82, 0.12, 0.88, ("joyful", "groovy")),
    ("Soft Alarm", "June Harbor", "Bright", ("pop", "electronic"), "en", 2024, 194, 124, 0.82, 0.78, 0.08, 0.76, ("energetic", "joyful")),
    ("Pier Lights", "Silver Coast", "Salt", ("alt", "indie"), "en", 2022, 241, 110, 0.52, 0.50, 0.28, 0.42, ("nocturnal", "dreamy")),
    ("Undertow", "Silver Coast", "Salt", ("alt", "rock"), "en", 2022, 226, 128, 0.72, 0.46, 0.14, 0.26, ("tense", "melancholic")),
    ("Thermal", "Kite Static", "Lift", ("electronic",), "en", 2023, 252, 128, 0.76, 0.78, 0.08, 0.66, ("energetic", "dreamy")),
    ("Glass Elevator", "Kite Static", "Lift", ("electronic", "ambient"), "en", 2023, 268, 118, 0.46, 0.58, 0.20, 0.50, ("focused", "calm")),
    ("Afterimage", "Low Voltage Club", "Night Grid", ("electronic",), "en", 2021, 236, 122, 0.70, 0.84, 0.05, 0.44, ("nocturnal", "groovy")),
    ("Circuit Saint", "Low Voltage Club", "Night Grid", ("electronic",), "en", 2021, 244, 132, 0.88, 0.86, 0.04, 0.52, ("energetic", "aggressive")),
    ("Slow Phosphor", "Amber Circuit", "Greenhouse", ("ambient", "electronic"), "en", 2022, 301, 78, 0.20, 0.26, 0.62, 0.48, ("calm", "dreamy", "focused")),
    ("Leaf Voltage", "Amber Circuit", "Greenhouse", ("ambient", "electronic"), "en", 2022, 286, 88, 0.28, 0.32, 0.66, 0.60, ("calm", "hopeful")),
    ("Blue Lobby", "Elias Ward Quartet", "After Set", ("jazz",), "en", 2017, 274, 108, 0.38, 0.48, 0.62, 0.40, ("nocturnal", "calm")),
    ("Quarter Past Rain", "Elias Ward Quartet", "After Set", ("jazz",), "en", 2017, 291, 92, 0.32, 0.42, 0.70, 0.32, ("melancholic", "romantic")),
    ("Velvet Peel", "Night Orchard", "Late Menu", ("jazz", "soul"), "en", 2019, 248, 102, 0.48, 0.64, 0.38, 0.66, ("romantic", "groovy")),
    ("Citrus Room", "Night Orchard", "Late Menu", ("soul", "jazz"), "en", 2019, 221, 116, 0.60, 0.72, 0.26, 0.80, ("joyful", "groovy")),
    ("Unsent Prelude", "Soren Vale", "Studies for Evening", ("classical", "ambient"), "en", 2016, 312, 72, 0.14, 0.16, 0.95, 0.30, ("calm", "melancholic")),
    ("Study in Warm Light", "Soren Vale", "Studies for Evening", ("classical", "ambient"), "en", 2016, 286, 76, 0.18, 0.20, 0.93, 0.58, ("calm", "hopeful", "focused")),
    ("Snow Desk", "Hanae Ito", "Window Pieces", ("classical", "ambient"), "ja", 2020, 298, 70, 0.12, 0.14, 0.97, 0.46, ("calm", "focused")),
    ("Paper Crane", "Hanae Ito", "Window Pieces", ("classical",), "ja", 2020, 264, 78, 0.20, 0.22, 0.92, 0.66, ("hopeful", "calm")),
    ("Last Train Home", "Hanae Ito", "Window Pieces", ("classical", "ambient"), "ja", 2021, 308, 74, 0.16, 0.18, 0.94, 0.26, ("nocturnal", "melancholic")),
    ("Fjord Mute", "Linnea Frost", "North Room", ("ambient",), "en", 2024, 334, 66, 0.10, 0.12, 0.90, 0.44, ("calm", "dreamy")),
    ("Birch Static", "Linnea Frost", "North Room", ("ambient", "lo-fi"), "en", 2024, 318, 82, 0.24, 0.22, 0.82, 0.50, ("focused", "calm")),
    ("Concrete Honey", "Cassian Rowe", "Block Party", ("hip-hop",), "en", 2022, 198, 96, 0.74, 0.80, 0.10, 0.58, ("groovy", "energetic")),
    ("No New Messages", "Cassian Rowe", "Block Party", ("hip-hop",), "en", 2022, 186, 90, 0.56, 0.68, 0.16, 0.30, ("nocturnal", "tense")),
    ("Low Ceiling", "Velvet District", "Satin", ("r&b",), "en", 2023, 224, 98, 0.48, 0.66, 0.26, 0.52, ("romantic", "nocturnal")),
    ("Gold Hour", "Velvet District", "Satin", ("r&b", "soul"), "en", 2023, 212, 106, 0.60, 0.72, 0.20, 0.76, ("romantic", "joyful")),
    ("Sunday Wire", "Marlowe Quinn", "Open Late", ("soul",), "en", 2018, 238, 100, 0.50, 0.58, 0.36, 0.72, ("hopeful", "groovy")),
    ("Red Envelope", "Marlowe Quinn", "Open Late", ("soul", "singer-songwriter"), "en", 2018, 226, 88, 0.34, 0.44, 0.54, 0.32, ("romantic", "melancholic")),
    ("Trail Coffee", "Cedar & Pine", "Switchback", ("folk",), "en", 2019, 218, 106, 0.40, 0.42, 0.84, 0.68, ("calm", "hopeful")),
    ("Creek Map", "Cedar & Pine", "Switchback", ("folk", "ambient"), "en", 2019, 242, 98, 0.32, 0.34, 0.88, 0.52, ("calm", "focused")),
    ("Apron Strings", "Willa Brooks", "Kitchen Songs", ("folk", "singer-songwriter"), "en", 2021, 204, 114, 0.48, 0.52, 0.74, 0.82, ("joyful", "calm")),
    ("Leave the Light", "Willa Brooks", "Kitchen Songs", ("folk", "singer-songwriter"), "en", 2021, 216, 84, 0.22, 0.28, 0.90, 0.24, ("melancholic", "calm")),
    ("Farol", "Luz Navarro", "Costa", ("latin", "pop"), "es", 2022, 208, 118, 0.72, 0.78, 0.22, 0.84, ("joyful", "groovy")),
    ("Marea Baja", "Luz Navarro", "Costa", ("latin", "singer-songwriter"), "es", 2022, 226, 94, 0.36, 0.44, 0.64, 0.56, ("romantic", "calm")),
    ("Patio", "Sol de Marzo", "Siesta", ("latin", "pop"), "es", 2020, 198, 122, 0.78, 0.82, 0.18, 0.86, ("joyful", "energetic")),
    ("Noche Clara", "Sol de Marzo", "Siesta", ("latin",), "es", 2020, 214, 100, 0.44, 0.56, 0.42, 0.60, ("nocturnal", "romantic")),
    ("Neon Homework", "Seo Haneul", "After School", ("k-pop", "pop"), "ko", 2024, 192, 126, 0.84, 0.86, 0.08, 0.82, ("joyful", "energetic")),
    ("Rainy Convenience Store", "Seo Haneul", "After School", ("k-pop", "indie"), "ko", 2024, 210, 98, 0.40, 0.48, 0.46, 0.34, ("melancholic", "dreamy")),
    ("Subway Bloom", "Midnight Seoul", "Line 2", ("electronic", "k-pop"), "ko", 2023, 234, 118, 0.58, 0.70, 0.14, 0.48, ("nocturnal", "dreamy")),
    ("Vinyl Umbrella", "Midnight Seoul", "Line 2", ("k-pop", "pop"), "ko", 2023, 206, 112, 0.64, 0.76, 0.16, 0.68, ("groovy", "hopeful")),
    ("Fenêtre", "Camille Duval", "Quartier", ("french-pop", "indie"), "fr", 2021, 218, 102, 0.42, 0.50, 0.58, 0.62, ("romantic", "dreamy")),
    ("Taximetre", "Camille Duval", "Quartier", ("french-pop",), "fr", 2021, 202, 116, 0.62, 0.68, 0.24, 0.50, ("groovy", "nocturnal")),
    ("Janela Aberta", "Rafael Costa", "Verão", ("latin", "folk"), "pt", 2019, 224, 108, 0.48, 0.52, 0.68, 0.74, ("calm", "joyful")),
    ("Areia", "Rafael Costa", "Verão", ("latin", "folk"), "pt", 2019, 236, 92, 0.30, 0.38, 0.80, 0.58, ("calm", "romantic")),
    ("Fault Line", "Glass Meridian", "Pressure", ("rock", "alt"), "en", 2020, 246, 138, 0.86, 0.50, 0.06, 0.38, ("energetic", "tense")),
    ("Silver Repair", "Glass Meridian", "Pressure", ("rock",), "en", 2020, 232, 128, 0.74, 0.54, 0.12, 0.64, ("hopeful", "energetic")),
    ("Heat Treat", "Red Kiln", "Furnace", ("rock", "alt"), "en", 2018, 214, 142, 0.90, 0.48, 0.05, 0.32, ("aggressive", "energetic")),
    ("Cooling Rack", "Red Kiln", "Furnace", ("alt", "rock"), "en", 2018, 228, 110, 0.56, 0.42, 0.18, 0.28, ("nocturnal", "tense")),
    ("Thorn Alloy", "Iron Petal", "Bloom & Rust", ("metal",), "en", 2022, 206, 158, 0.95, 0.40, 0.02, 0.22, ("aggressive", "tense")),
    ("Soft Rust", "Iron Petal", "Bloom & Rust", ("metal", "alt"), "en", 2022, 238, 134, 0.74, 0.36, 0.08, 0.30, ("melancholic", "energetic")),
    ("Page 42", "Tape Library", "Study Hall", ("lo-fi", "ambient"), "en", 2023, 188, 82, 0.28, 0.40, 0.64, 0.46, ("focused", "calm")),
    ("Highlighter", "Tape Library", "Study Hall", ("lo-fi",), "en", 2023, 176, 88, 0.32, 0.44, 0.58, 0.52, ("focused", "dreamy")),
    ("Delay Line", "Window Seat", "Commute", ("lo-fi", "ambient"), "en", 2024, 204, 76, 0.20, 0.34, 0.72, 0.44, ("calm", "nocturnal")),
    ("Overhead Bin", "Window Seat", "Commute", ("lo-fi",), "en", 2024, 198, 86, 0.30, 0.42, 0.66, 0.50, ("dreamy", "focused")),
]

_SPEECH = {
    "hip-hop": 0.16,
    "r&b": 0.09,
    "soul": 0.08,
    "pop": 0.07,
    "k-pop": 0.08,
    "bollywood": 0.09,
    "french-pop": 0.07,
    "latin": 0.07,
}
_INSTRUMENTAL = {
    "ambient": 0.84,
    "classical": 0.90,
    "lo-fi": 0.72,
    "electronic": 0.60,
    "jazz": 0.50,
    "metal": 0.12,
    "folk": 0.22,
    "singer-songwriter": 0.12,
}

FEATURE_SOURCE = "editorial_demo_not_from_audio"
OBSERVED = (
    "tempo",
    "energy",
    "danceability",
    "acousticness",
    "valence",
    "speechiness",
    "instrumentalness",
    "loudness",
    "musical_key",
    "mode",
    "genres",
    "language",
    "mood_tags",
)


def _speechiness(genres: tuple[str, ...]) -> float:
    return _SPEECH.get(genres[0], 0.045)


def _instrumentalness(genres: tuple[str, ...]) -> float:
    return _INSTRUMENTAL.get(genres[0], 0.18)


def build_demo_catalog() -> list[Track]:
    tracks: list[Track] = []
    for index, row in enumerate(_ROWS, start=1):
        title, artist, album, genres, language, year, seconds, tempo, energy, dance, acoustic, valence, moods = row
        minor = valence < 0.45 or "melancholic" in moods or "tense" in moods or "aggressive" in moods
        track = Track(
            id=f"mw-{index:03d}",
            title=title,
            artist=artist,
            album=album,
            genres=tuple(genres),
            language=language,
            year=int(year),
            duration_ms=int(seconds) * 1000,
            tempo=float(tempo),
            energy=float(energy),
            danceability=float(dance),
            acousticness=float(acoustic),
            valence=float(valence),
            speechiness=float(_speechiness(genres)),
            instrumentalness=float(_instrumentalness(genres)),
            loudness=float(np.round(-7.5 - (1.0 - energy) * 16.0, 2)),
            musical_key=editorial_key(artist),
            mode=0 if minor else 1,
            mood_tags=tuple(moods),
            feature_source=FEATURE_SOURCE,
            observed=OBSERVED,
        )
        validate_track_vocab(track)
        tracks.append(track)
    return tracks
