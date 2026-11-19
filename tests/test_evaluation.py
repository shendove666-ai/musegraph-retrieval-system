"""Check metric arithmetic and validation of relevance grades."""

import io
import json
from math import log2

import pytest

from musegraph.evaluation import Metrics, metrics_at_k, read_judgments


def test_metrics_use_unique_ranks_and_fixed_cutoff():
    metrics = metrics_at_k(["b", "b", "unknown", "a"], {"a": 3, "b": 1, "c": 1}, 3)
    assert metrics.precision == pytest.approx(2 / 3)
    assert metrics.recall == pytest.approx(2 / 3)
    assert metrics.ndcg == pytest.approx((1 + 7 / log2(4)) / (7 + 1 / log2(3) + 1 / log2(4)))
    assert metrics_at_k(["a"], {"a": 3}, 3).precision == pytest.approx(1 / 3)
    assert metrics_at_k([], {}, 3) == Metrics(0, 0, 0)
    with pytest.raises(ValueError):
        metrics_at_k([], {}, 0)


@pytest.mark.parametrize("grades", [{"a": True}, {"a": 4}, {"missing": 1}])
def test_invalid_qrels(grades):
    stream = io.StringIO(json.dumps([{
        "id": "q1", "query": "music", "category": "topic", "grades": grades,
    }]))
    with pytest.raises(ValueError, match="unknown document or a grade"):
        read_judgments(stream, {"a"})
