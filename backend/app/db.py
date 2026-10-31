"""SQLite access for the live listener. Synthetic demo users are not stored here."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    explicit_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    track_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ts INTEGER NOT NULL,
                    listen_ms INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    listen_ratio REAL NOT NULL DEFAULT 0,
                    origin TEXT NOT NULL DEFAULT 'live'
                );
                CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, ts);
                CREATE TABLE IF NOT EXISTS reactions (
                    user_id TEXT NOT NULL,
                    track_id TEXT NOT NULL,
                    reaction TEXT NOT NULL,
                    PRIMARY KEY (user_id, track_id)
                );
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id INTEGER NOT NULL,
                    track_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    added_at TEXT NOT NULL,
                    PRIMARY KEY (playlist_id, track_id),
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS catalog_extra (
                    track_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS spotify_playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS spotify_playlist_tracks (
                    playlist_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    spotify_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    image TEXT,
                    preview_url TEXT,
                    spotify_url TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    PRIMARY KEY (playlist_id, spotify_id),
                    FOREIGN KEY (playlist_id) REFERENCES spotify_playlists(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS ytmusic_playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ytmusic_playlist_tracks (
                    playlist_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    album TEXT NOT NULL,
                    image TEXT,
                    watch_url TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    PRIMARY KEY (playlist_id, video_id),
                    FOREIGN KEY (playlist_id) REFERENCES ytmusic_playlists(id) ON DELETE CASCADE
                );
                """
            )

    def get_profile(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT explicit_json, updated_at FROM profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {"explicit": json.loads(row["explicit_json"]), "updated_at": row["updated_at"]}

    def save_profile(self, user_id: str, explicit: dict, updated_at: str) -> None:
        payload = json.dumps(explicit)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO profiles (user_id, explicit_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    explicit_json = excluded.explicit_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, payload, updated_at),
            )

    def delete_profile(self, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM reactions WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM playlists WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM spotify_playlists WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM ytmusic_playlists WHERE user_id = ?", (user_id,))

    def clear_behavior(self, user_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM reactions WHERE user_id = ?", (user_id,))

    def add_event(self, user_id: str, track_id: str, event_type: str, ts: int, listen_ms: int, duration_ms: int, listen_ratio: float) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO events (user_id, track_id, event_type, ts, listen_ms, duration_ms, listen_ratio, origin)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'live')
                """,
                (user_id, track_id, event_type, ts, listen_ms, duration_ms, listen_ratio),
            )
            return int(cursor.lastrowid)

    def delete_latest_reaction_event(self, user_id: str, track_id: str) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id FROM events
                WHERE user_id = ? AND track_id = ? AND event_type IN ('like', 'dislike')
                ORDER BY ts DESC, id DESC LIMIT 1
                """,
                (user_id, track_id),
            ).fetchone()
            if row is not None:
                connection.execute("DELETE FROM events WHERE id = ?", (row["id"],))

    def list_events(self, user_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, track_id, event_type, ts, listen_ms, duration_ms, listen_ratio, origin
                FROM events WHERE user_id = ? ORDER BY ts ASC, id ASC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_reaction(self, user_id: str, track_id: str, reaction: str) -> None:
        with self._connect() as connection:
            if reaction == "none":
                connection.execute(
                    "DELETE FROM reactions WHERE user_id = ? AND track_id = ?",
                    (user_id, track_id),
                )
                return
            connection.execute(
                """
                INSERT INTO reactions (user_id, track_id, reaction)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, track_id) DO UPDATE SET reaction = excluded.reaction
                """,
                (user_id, track_id, reaction),
            )

    def reactions(self, user_id: str) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT track_id, reaction FROM reactions WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {row["track_id"]: row["reaction"] for row in rows}

    def create_playlist(self, user_id: str, name: str, created_at: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO playlists (user_id, name, created_at) VALUES (?, ?, ?)",
                (user_id, name, created_at),
            )
            return int(cursor.lastrowid)

    def list_playlists(self, user_id: str) -> list[dict]:
        with self._connect() as connection:
            playlists = connection.execute(
                "SELECT id, name, created_at FROM playlists WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
            result = []
            for playlist in playlists:
                tracks = connection.execute(
                    """
                    SELECT track_id FROM playlist_tracks
                    WHERE playlist_id = ? ORDER BY position ASC, added_at ASC
                    """,
                    (playlist["id"],),
                ).fetchall()
                result.append(
                    {
                        "id": playlist["id"],
                        "name": playlist["name"],
                        "created_at": playlist["created_at"],
                        "track_ids": [row["track_id"] for row in tracks],
                    }
                )
        return result

    def add_playlist_track(self, playlist_id: int, user_id: str, track_id: str, added_at: str) -> bool:
        with self._connect() as connection:
            owner = connection.execute(
                "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            ).fetchone()
            if owner is None:
                return False
            position_row = connection.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 AS next_pos FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position, added_at)
                VALUES (?, ?, ?, ?)
                """,
                (playlist_id, track_id, int(position_row["next_pos"]), added_at),
            )
        return True

    def remove_playlist_track(self, playlist_id: int, user_id: str, track_id: str) -> bool:
        with self._connect() as connection:
            owner = connection.execute(
                "SELECT id FROM playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            ).fetchone()
            if owner is None:
                return False
            connection.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                (playlist_id, track_id),
            )
        return True

    def delete_playlist(self, playlist_id: int, user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            )
            return cursor.rowcount > 0

    def save_spotify_playlist(self, user_id: str, name: str, prompt: str, created_at: str, tracks: list[dict]) -> dict:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO spotify_playlists (user_id, name, prompt, created_at) VALUES (?, ?, ?, ?)",
                (user_id, name, prompt, created_at),
            )
            playlist_id = int(cursor.lastrowid)
            for position, track in enumerate(tracks):
                connection.execute(
                    """
                    INSERT INTO spotify_playlist_tracks (
                        playlist_id, position, spotify_id, title, artist, album,
                        image, preview_url, spotify_url, duration_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        playlist_id,
                        position,
                        track["spotify_id"],
                        track["title"],
                        track["artist"],
                        track["album"],
                        track.get("image"),
                        track.get("preview_url"),
                        track["spotify_url"],
                        int(track["duration_ms"]),
                    ),
                )
        saved = self.get_spotify_playlist(user_id, playlist_id)
        if saved is None:
            raise RuntimeError("Saved Spotify playlist could not be read back.")
        return saved

    def list_spotify_playlists(self, user_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM spotify_playlists WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        playlists = []
        for row in rows:
            playlist = self.get_spotify_playlist(user_id, int(row["id"]))
            if playlist:
                playlists.append(playlist)
        return playlists

    def get_spotify_playlist(self, user_id: str, playlist_id: int) -> dict | None:
        with self._connect() as connection:
            playlist = connection.execute(
                "SELECT id, name, prompt, created_at FROM spotify_playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            ).fetchone()
            if playlist is None:
                return None
            tracks = connection.execute(
                """
                SELECT spotify_id, title, artist, album, image, preview_url, spotify_url, duration_ms
                FROM spotify_playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position ASC
                """,
                (playlist_id,),
            ).fetchall()
        return {
            "id": playlist["id"],
            "name": playlist["name"],
            "prompt": playlist["prompt"],
            "created_at": playlist["created_at"],
            "tracks": [dict(track) for track in tracks],
        }

    def delete_spotify_playlist(self, playlist_id: int, user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM spotify_playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            )
            return cursor.rowcount > 0

    def save_ytmusic_playlist(self, user_id: str, name: str, prompt: str, created_at: str, tracks: list[dict]) -> dict:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO ytmusic_playlists (user_id, name, prompt, created_at) VALUES (?, ?, ?, ?)",
                (user_id, name, prompt, created_at),
            )
            playlist_id = int(cursor.lastrowid)
            for position, track in enumerate(tracks):
                connection.execute(
                    """
                    INSERT INTO ytmusic_playlist_tracks (
                        playlist_id, position, video_id, title, artist, album, image, watch_url, duration_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        playlist_id,
                        position,
                        track["video_id"],
                        track["title"],
                        track["artist"],
                        track["album"],
                        track.get("image"),
                        track["watch_url"],
                        int(track["duration_ms"]),
                    ),
                )
        saved = self.get_ytmusic_playlist(user_id, playlist_id)
        if saved is None:
            raise RuntimeError("Saved YouTube Music playlist could not be read back.")
        return saved

    def list_ytmusic_playlists(self, user_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM ytmusic_playlists WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        playlists = []
        for row in rows:
            playlist = self.get_ytmusic_playlist(user_id, int(row["id"]))
            if playlist:
                playlists.append(playlist)
        return playlists

    def get_ytmusic_playlist(self, user_id: str, playlist_id: int) -> dict | None:
        with self._connect() as connection:
            playlist = connection.execute(
                "SELECT id, name, prompt, created_at FROM ytmusic_playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            ).fetchone()
            if playlist is None:
                return None
            tracks = connection.execute(
                """
                SELECT video_id, title, artist, album, image, watch_url, duration_ms
                FROM ytmusic_playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position ASC
                """,
                (playlist_id,),
            ).fetchall()
        return {
            "id": playlist["id"],
            "name": playlist["name"],
            "prompt": playlist["prompt"],
            "created_at": playlist["created_at"],
            "tracks": [dict(track) for track in tracks],
        }

    def delete_ytmusic_playlist(self, playlist_id: int, user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ytmusic_playlists WHERE id = ? AND user_id = ?",
                (playlist_id, user_id),
            )
            return cursor.rowcount > 0

    def save_catalog_extra(self, track_id: str, payload: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO catalog_extra (track_id, payload) VALUES (?, ?)
                ON CONFLICT(track_id) DO UPDATE SET payload = excluded.payload
                """,
                (track_id, json.dumps(payload)),
            )

    def list_catalog_extra(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM catalog_extra ORDER BY track_id").fetchall()
        found = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                found.append(payload)
        return found

    def get_kv(self, key: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def set_kv(self, key: str, value: dict) -> None:
        payload = json.dumps(value)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO kv (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, payload),
            )
