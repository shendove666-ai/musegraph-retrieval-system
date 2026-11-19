"""Check token spans, term weighting, and local fingerprint guarantees."""

import pytest

from musegraph.algorithms.fingerprint import compare, fingerprints
from musegraph.algorithms.text import scan, terms
from musegraph.algorithms.tfidf import Tfidf


def test_unicode_token_offsets():
    text = "Cafe\u0301’s VIOLA, Dvořák."
    tokens = scan(text)
    assert terms(text) == ["café's", "viola", "dvořák"]
    assert text[tokens[0].start:tokens[0].end] == "Cafe\u0301’s"


def test_tfidf_reweights_rare_terms():
    index = Tfidf(["viola bow", "viola viola cello", "viola tuning"])
    scores = index.score("viola cello")
    assert scores[1][0] > scores[0][0]
    assert scores[1][1] == ("cello", "viola")
    assert index.score("harpsichord") == [(0, ())] * 3
    assert Tfidf([]).score("viola") == []


def test_rightmost_hash_wins_ties():
    selected = fingerprints("a a a a a a a a a", k=2, window=3)
    assert selected[("a", "a")].start == 4
    assert len(selected) == 1


def test_verified_shared_run_survives_different_contexts():
    left = "Preface. A cadence in the new key confirms the move. Appendix."
    right = "Introduction! A CADENCE in the new key confirms the move? Coda."
    comparison = compare(left, right)
    assert comparison.shared >= 1
    for left_span, right_span in comparison.evidence:
        assert terms(left[left_span.start:left_span.end]) == terms(right[right_span.start:right_span.end])
    assert compare(left, left).score == 1
    assert compare("short phrase", "short phrase").score == 0
    with pytest.raises(ValueError):
        fingerprints(left, window=0)


def test_ascii_token_boundaries_preserve_apostrophes_and_offsets():
    text = "'A2's a''b _C-9\tJohn's' ."
    tokens = scan(text)
    assert [token.term for token in tokens] == ["a2's", "a", "b", "c", "9", "john's"]
    assert [text[token.start:token.end] for token in tokens] == ["A2's", "a", "b", "C", "9", "John's"]
