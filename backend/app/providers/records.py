"""Serialize a track so a provider result can be reloaded without the network."""

from __future__ import annotations

from app.data.catalog import Track


def track_record(track: Track) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "genres": list(track.genres),
        "language": track.language,
        "year": track.year,
        "duration_ms": track.duration_ms,
        "tempo": track.tempo,
        "energy": track.energy,
        "danceability": track.danceability,
        "acousticness": track.acousticness,
        "valence": track.valence,
        "speechiness": track.speechiness,
        "instrumentalness": track.instrumentalness,
        "loudness": track.loudness,
        "musical_key": track.musical_key,
        "mode": track.mode,
        "mood_tags": list(track.mood_tags),
        "feature_source": track.feature_source,
        "observed": list(track.observed),
        "provider": track.provider,
        "artwork_url": track.artwork_url,
        "preview_url": track.preview_url,
        "external_url": track.external_url,
        "embed_url": track.embed_url,
        "playback_kind": track.playback_kind,
        "preview_duration_ms": track.preview_duration_ms,
        "song_duration_ms": track.song_duration_ms,
        "genre_labels": list(track.genre_labels),
    }


def track_from_record(data: dict) -> Track:
    return Track(
        id=str(data["id"]),
        title=str(data["title"]),
        artist=str(data["artist"]),
        album=str(data.get("album") or ""),
        genres=tuple(data.get("genres") or ()),
        language=str(data.get("language") or ""),
        year=int(data.get("year") or 0),
        duration_ms=int(data.get("duration_ms") or 0),
        tempo=data.get("tempo"),
        energy=data.get("energy"),
        danceability=data.get("danceability"),
        acousticness=data.get("acousticness"),
        valence=data.get("valence"),
        speechiness=data.get("speechiness"),
        instrumentalness=data.get("instrumentalness"),
        loudness=data.get("loudness"),
        musical_key=data.get("musical_key"),
        mode=data.get("mode"),
        mood_tags=tuple(data.get("mood_tags") or ()),
        feature_source=str(data.get("feature_source") or "catalog_metadata"),
        observed=tuple(data.get("observed") or ()),
        provider=str(data.get("provider") or "catalog"),
        artwork_url=data.get("artwork_url"),
        preview_url=data.get("preview_url"),
        external_url=data.get("external_url"),
        embed_url=data.get("embed_url"),
        playback_kind=str(data.get("playback_kind") or ""),
        preview_duration_ms=data.get("preview_duration_ms"),
        song_duration_ms=data.get("song_duration_ms"),
        genre_labels=tuple(data.get("genre_labels") or ()),
    )
