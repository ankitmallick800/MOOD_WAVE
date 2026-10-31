import json
import urllib.error
from email.message import Message

from app.providers.lrclib import choose_record, clear_cache, lookup_lyrics, parse_synced


def test_parse_synced_keeps_timestamps_and_blank_breaks():
    lines = parse_synced("[00:11.18] इश्क़ में दिल\n[00:18.80] \n[01:02.00][01:05.50] again")
    assert lines[0] == {"at_ms": 11180, "text": "इश्क़ में दिल"}
    assert lines[1]["at_ms"] == 18800
    assert lines[1]["text"] == ""
    assert [item["at_ms"] for item in lines[2:]] == [62000, 65500]
    assert lines[2]["text"] == "again"


def test_choose_record_rejects_a_different_title_and_prefers_synced():
    records = [
        {"trackName": "Other", "artistName": "Arijit Singh", "duration": 188, "syncedLyrics": "[00:01.00] no"},
        {"trackName": "Chaleya (Remix)", "artistName": "Arijit Singh", "duration": 188, "syncedLyrics": "[00:01.00] remix"},
        {"trackName": "Chaleya", "artistName": "Arijit Singh", "duration": 200, "plainLyrics": "plain"},
        {"trackName": "Chaleya", "artistName": "Arijit Singh", "duration": 190, "syncedLyrics": "[00:01.00] yes"},
    ]
    chosen = choose_record(records, "Chaleya (From \"Jawan\")", "Arijit Singh, Shilpa Rao", 188)
    assert chosen is not None
    assert chosen["syncedLyrics"].endswith("yes")


def test_lookup_reads_search_and_caches():
    clear_cache()
    calls = {"n": 0}

    class Response:
        status = 200

        def __init__(self, payload):
            self.payload = payload

        def read(self, _limit):
            return json.dumps(self.payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def opener(request, timeout=6):
        calls["n"] += 1
        assert "Moodwave/1.0" in (request.get_header("User-agent") or "")
        url = request.full_url
        assert url.startswith("https://lrclib.net/api/")
        assert timeout == 6
        if "/search?" not in url:
            raise urllib.error.HTTPError(url, 404, "missing", Message(), None)
        return Response(
            [
                {
                    "trackName": "Chaleya",
                    "artistName": "Arijit Singh",
                    "duration": 188,
                    "instrumental": False,
                    "syncedLyrics": "[00:11.18] इश्क़ में दिल\n[00:21.29] मिटा दे",
                    "plainLyrics": "ignored when synced",
                }
            ]
        )

    first = lookup_lyrics("Chaleya", "Arijit Singh", "Jawan", 188000, opener=opener)
    second = lookup_lyrics("Chaleya", "Arijit Singh", "Jawan", 188000, opener=opener)
    assert first["found"] is True
    assert first["source"] == "LRCLIB"
    assert first["synced"] is True
    assert first["plain"] == "ignored when synced"
    assert first["lines"][0]["text"] == "इश्क़ में दिल"
    assert second == first
    assert calls["n"] == 1
