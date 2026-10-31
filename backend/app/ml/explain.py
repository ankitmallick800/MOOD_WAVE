"""Explanations built only from scores and profile facts already computed."""

from __future__ import annotations

from app.data.catalog import Track
from app.ml.profile import ExplicitProfile, InferredProfile
from app.ml.vocabulary import LANGUAGE_LABELS


def explain_recommendation(
    track: Track,
    components: dict[str, float | None],
    weights_used: dict[str, float],
    explicit: ExplicitProfile,
    inferred: InferredProfile,
    mood: str | None,
    mood_mode: str | None,
    source_mood: str | None,
    target_mood: str | None,
    neighbor: dict | None,
    strategy: str,
    audience: str = "synthetic",
) -> list[str]:
    if strategy == "popularity":
        if audience == "synthetic":
            return [
                "Ranked by how often this track is played in the labeled synthetic demo listener set."
            ]
        return ["Ranked by play counts saved in this app."]
    if strategy == "collaborative":
        lines = [_collaborative_sentence(neighbor, audience)]
        return [line for line in lines if line]
    if strategy == "collaborative_svd":
        if audience == "synthetic":
            return [
                "Ranked by a TruncatedSVD factorization of the synthetic demo interaction matrix."
            ]
        return ["Ranked by a TruncatedSVD factorization of listening saved in this app."]

    contributions = []
    for name, weight in weights_used.items():
        value = components.get(name)
        if value is None:
            continue
        contributions.append((weight * value, name))
    contributions.sort(reverse=True)

    sentences: list[str] = []
    for _, name in contributions:
        sentence = _sentence(
            name,
            track,
            explicit,
            inferred,
            mood_mode,
            source_mood,
            target_mood,
            neighbor,
            audience,
        )
        if sentence and sentence not in sentences:
            sentences.append(sentence)
        if len(sentences) == 2:
            break
    if not sentences:
        if _has_audio(track):
            sentences.append("Ranked from the available catalog features for your profile.")
        else:
            sentences.append("Ranked from catalog metadata. Tempo, energy, and mood are unknown for this song.")
    return sentences


def _sentence(
    name: str,
    track: Track,
    explicit: ExplicitProfile,
    inferred: InferredProfile,
    mood_mode: str | None,
    source_mood: str | None,
    target_mood: str | None,
    neighbor: dict | None,
    audience: str,
) -> str | None:
    if name == "content":
        shared = [genre for genre in track.genres if genre in explicit.genres]
        if not shared:
            shared = [
                genre
                for genre in track.genres
                if inferred.genre_affinity.get(genre, 0.0) > 0.2
            ]
        if shared:
            label = _join(shared[:2])
            if any(genre in explicit.genres for genre in shared):
                return f"Matches your selected {label} preference."
            return f"Recommended because your listening history leans toward {label}."
        if _has_audio(track):
            return "Close to your preferred tempo, energy, and acoustic profile."
        return None
    if name == "collaborative":
        return _collaborative_sentence(neighbor, audience)
    if name == "preference":
        plays = inferred.plays_by_artist.get(track.artist, 0)
        if track.artist in explicit.artists and plays >= 3:
            return f"Recommended because you have played {track.artist} {plays} times and chose them in onboarding."
        if track.artist in explicit.artists:
            return f"Matches your selected artist, {track.artist}."
        if plays >= 3:
            return f"Recommended because you have played {track.artist} {plays} times."
        if inferred.artist_affinity.get(track.artist, 0.0) > 0.25:
            return f"Aligns with your affinity for {track.artist}."
        language = LANGUAGE_LABELS.get(track.language, track.language)
        if track.language in explicit.languages:
            return f"Matches your selected {language} preference."
        shared = [genre for genre in track.genres if genre in explicit.genres]
        if shared:
            return f"Recommended because you selected {shared[0]}."
        if _has_audio(track):
            return "Close to the energy and valence range in your profile."
        return None
    if name == "mood":
        if mood_mode == "shift" and source_mood and target_mood and source_mood != target_mood:
            return f"Chosen to shift a {source_mood} listening mood toward {target_mood}."
        if target_mood:
            return f"Chosen to match your current {target_mood} listening mood."
        return None
    if name == "discovery":
        known = track.artist in explicit.artists or inferred.plays_by_artist.get(track.artist, 0) > 0
        if known:
            return f"Fits a familiar artist, {track.artist}, relative to your history."
        if _has_audio(track):
            return f"A new artist, {track.artist}, with catalog features near your taste."
        return f"A new artist, {track.artist}."
    return None


def _has_audio(track: Track) -> bool:
    return any(value is not None for value in (track.tempo, track.energy, track.danceability, track.acousticness, track.valence))


def _collaborative_sentence(neighbor: dict | None, audience: str) -> str:
    if audience != "synthetic":
        if neighbor:
            return f"Listeners saved in this app who played “{neighbor['title']}” also played this."
        return "Collaborative score from listening saved in this app."
    if neighbor:
        return (
            f"Listeners in the synthetic demo set who played “{neighbor['title']}” "
            "also played this. That set is generated, not a real audience."
        )
    return "Collaborative score from co-listening patterns in the labeled synthetic demo set."


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{items[0]} and {items[1]}"
