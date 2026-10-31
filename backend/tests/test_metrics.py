import math

from app.ml.metrics import hit_rate_at_k, ndcg_at_k, precision_at_k, recall_at_k


def test_precision_recall_and_hit_rate():
    recommended = ["a", "b", "c", "d"]
    relevant = {"b", "d", "e"}
    assert precision_at_k(recommended, relevant, 4) == 0.5
    assert recall_at_k(recommended, relevant, 4) == 2 / 3
    assert hit_rate_at_k(recommended, relevant, 1) == 0.0
    assert hit_rate_at_k(recommended, relevant, 2) == 1.0


def test_ndcg_matches_hand_calculation():
    recommended = ["a", "b", "c"]
    grades = {"a": 1.0, "c": 1.0}
    dcg = 1.0 / math.log2(2) + 0.0 / math.log2(3) + 1.0 / math.log2(4)
    idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)
    assert ndcg_at_k(recommended, grades, 3) == dcg / idcg


def test_ndcg_empty_relevance_is_missing():
    assert ndcg_at_k(["a"], {}, 3) is None
