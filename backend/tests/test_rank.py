import numpy as np

from app.data.catalog import diversity_vector
from app.data.demo_catalog import build_demo_catalog
from app.ml.explain import explain_recommendation
from app.ml.features import FeatureBlocks, masked_weighted_cosine
from app.ml.hybrid import ScoredTrack, _diversify, combine
from app.ml.hybrid import rank_tracks
from app.ml.mood import interpret_expression, resolve_target
from app.ml.profile import ExplicitProfile, InferredProfile, apply_event, blended_characteristics
from app.ml.vocabulary import DEFAULT_GROUP_WEIGHTS, DEFAULT_WEIGHTS


def _profile() -> ExplicitProfile:
    return ExplicitProfile(
        artists=["Anik Sen"],
        genres=["bengali-modern", "indie"],
        languages=["bn"],
        purpose="relax",
        discovery=0.25,
        energy=0.34,
        danceability=0.36,
        acousticness=0.74,
        valence=0.4,
        tempo=0.32,
    )


def test_missing_components_are_dropped_not_zeroed():
    components = {
        "content": 0.8,
        "collaborative": None,
        "preference": 0.4,
        "mood": None,
        "discovery": None,
    }
    score, used = combine(components, DEFAULT_WEIGHTS)
    assert set(used) == {"content", "preference"}
    assert abs(sum(used.values()) - 1.0) < 1e-9
    expected = (0.34 * 0.8 + 0.22 * 0.4) / (0.34 + 0.22)
    assert abs(score - expected) < 1e-9
    # Treating the missing weights as zeros would shrink the score.
    treated_as_zero = 0.34 * 0.8 + 0.22 * 0.4
    assert score > treated_as_zero


def test_masked_cosine_ignores_unobserved_dimension():
    left = FeatureBlocks(
        blocks={
            "numeric": np.array([0.2, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            "genre": np.zeros(1),
            "language": np.zeros(1),
            "mood": np.zeros(1),
        },
        masks={
            "numeric": np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            "genre": np.zeros(1),
            "language": np.zeros(1),
            "mood": np.zeros(1),
        },
    )
    right = FeatureBlocks(
        blocks={
            "numeric": np.array([0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            "genre": np.zeros(1),
            "language": np.zeros(1),
            "mood": np.zeros(1),
        },
        masks={
            "numeric": np.array([1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            "genre": np.zeros(1),
            "language": np.zeros(1),
            "mood": np.zeros(1),
        },
    )
    weights = {"numeric": 1.0, "genre": 1.0, "language": 1.0, "mood": 1.0}
    # Only the first coordinate is observed on both sides, and those values match.
    assert masked_weighted_cosine(left, right, weights) == 1.0


def test_content_ranker_prefers_matching_language_and_genre():
    tracks = build_demo_catalog()
    ranked, meta = rank_tracks(
        tracks,
        _profile(),
        InferredProfile.empty(),
        collab_scores=None,
        pop_scores={track.id: 0.2 for track in tracks},
        neighbor_for=None,
        strategy="content",
        diversify=False,
        limit=5,
        mood=None,
    )
    assert meta["ranking_mode"] == "content"
    top = ranked[0].track
    assert top.language == "bn"
    assert "bengali-modern" in top.genres or "indie" in top.genres
    assert ranked[0].explanations
    blob = " ".join(ranked[0].explanations).lower()
    assert "bengali" in blob or "indie" in blob


def test_cold_start_hybrid_withholds_collaborative_score():
    tracks = build_demo_catalog()
    ranked, meta = rank_tracks(
        tracks,
        _profile(),
        InferredProfile.empty(),
        collab_scores=None,
        pop_scores={track.id: 0.2 for track in tracks},
        neighbor_for=None,
        strategy="hybrid",
        diversify=False,
        limit=8,
    )
    assert meta["ranking_mode"] == "cold_start_content"
    assert all(item.components["collaborative"] is None for item in ranked)
    assert all("collaborative" not in item.weights_used for item in ranked)


def test_artist_cap_limits_a_single_artist():
    tracks = build_demo_catalog()
    anik = [track for track in tracks if track.artist == "Anik Sen"]
    others = [track for track in tracks if track.artist != "Anik Sen"][:3]
    scored = []
    for index, track in enumerate(anik + others):
        score = 0.95 - index * 0.01 if track.artist == "Anik Sen" else 0.5
        scored.append(
            ScoredTrack(
                track=track,
                score=score,
                components={"content": score, "collaborative": None, "preference": None, "mood": None, "discovery": None},
                weights_used={"content": 1.0},
                explanations=[],
                vector=diversity_vector(track),
            )
        )
    chosen = _diversify(scored, lam=1.0, artist_cap=2, limit=4)
    assert sum(1 for item in chosen if item.track.artist == "Anik Sen") <= 2
    assert len(chosen) == 4


def test_one_like_does_not_replace_the_profile():
    tracks = {track.id: track for track in build_demo_catalog()}
    track = next(item for item in tracks.values() if item.energy is not None and item.energy > 0.8)
    inferred = InferredProfile.empty()
    apply_event(inferred, track, "like", 1.0)
    genre = track.genres[0]
    assert 0 < inferred.genre_affinity[genre] < 0.35
    assert inferred.confidence < 0.15
    explicit = ExplicitProfile(
        artists=[],
        genres=["folk"],
        languages=["en"],
        purpose="focus",
        discovery=0.5,
        energy=0.5,
        danceability=0.5,
        acousticness=0.5,
        valence=0.5,
        tempo=0.5,
    )
    blended = blended_characteristics(explicit, inferred)
    assert abs(blended["energy"] - 0.5) < 0.08


def test_shift_mood_changes_the_target():
    assert resolve_target("sad", "match") == ("sad", "sad")
    assert resolve_target("sad", "shift") == ("sad", "hopeful")
    assert resolve_target("angry", "shift")[1] == "calm"


def test_unmapped_expressions_do_not_invent_a_mood():
    fearful = interpret_expression({"fearful": 0.92, "neutral": 0.08})
    assert fearful["uncertain"] is True
    assert fearful["suggested_mood"] is None
    assert fearful["images_stored"] is False
    happy = interpret_expression({"happy": 0.81, "neutral": 0.19})
    assert happy["suggested_mood"] == "happy"
    weak = interpret_expression({"happy": 0.4, "neutral": 0.3, "sad": 0.3})
    assert weak["uncertain"] is True
    assert weak["suggested_mood"] is None


def test_explanation_does_not_claim_an_unrelated_genre():
    track = next(item for item in build_demo_catalog() if "metal" in item.genres)
    explicit = _profile()
    text = " ".join(
        explain_recommendation(
            track,
            {"content": 0.2, "collaborative": None, "preference": 0.1, "mood": None, "discovery": 0.9},
            {"content": 0.2, "preference": 0.1, "discovery": 0.7},
            explicit,
            InferredProfile.empty(),
            None,
            None,
            None,
            None,
            None,
            "hybrid",
        )
    )
    assert "metal" not in text
    assert "Anik Sen" not in text or "new artist" in text.lower() or "Iron Petal" in text


def test_group_weights_change_similarity():
    tracks = build_demo_catalog()
    profile = _profile()
    from app.data.catalog import profile_blocks, track_blocks

    listener = profile_blocks(profile, InferredProfile.empty())
    bengali = next(track for track in tracks if track.language == "bn" and "bengali-modern" in track.genres)
    metal = next(track for track in tracks if "metal" in track.genres)
    base = masked_weighted_cosine(listener, track_blocks(bengali), DEFAULT_GROUP_WEIGHTS)
    heavy_language = dict(DEFAULT_GROUP_WEIGHTS)
    heavy_language["language"] = 8.0
    boosted = masked_weighted_cosine(listener, track_blocks(bengali), heavy_language)
    metal_score = masked_weighted_cosine(listener, track_blocks(metal), DEFAULT_GROUP_WEIGHTS)
    assert base is not None and boosted is not None and metal_score is not None
    assert base > metal_score
    assert boosted >= base
