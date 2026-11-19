"""Select stable word fingerprints and verify shared normalized phrases."""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import blake2b

from .text import scan

GRAM_SIZE = 5
WINDOW_SIZE = 4


@dataclass(frozen=True, slots=True)
class Fingerprint:
    words: Sequence[str]
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Comparison:
    score: float
    shared: int
    left_count: int
    right_count: int
    evidence: Sequence[tuple[Fingerprint, Fingerprint]]


def fingerprints(
    text: str, k: int = GRAM_SIZE, window: int = WINDOW_SIZE
) -> dict[Sequence[str], Fingerprint]:
    if k < 1 or window < 1:
        raise ValueError("Gram and window sizes must be positive.")
    tokens = scan(text)
    gram_count = len(tokens) - k + 1
    if gram_count < 1:
        return {}

    width = min(window, gram_count)
    minima = deque()
    selected = {}
    previous_minimum_index = -1
    for gram_index in range(gram_count):
        gram_tokens = tokens[gram_index:gram_index + k]
        words = tuple(token.term for token in gram_tokens)
        digest = blake2b(" ".join(words).encode("utf-8"), digest_size=8).digest()
        while minima and minima[-1][1] >= digest:
            minima.pop()
        minima.append((gram_index, digest, Fingerprint(words, gram_tokens[0].start, gram_tokens[-1].end)))
        if minima[0][0] <= gram_index - width:
            minima.popleft()
        if gram_index >= width - 1 and minima[0][0] != previous_minimum_index:
            previous_minimum_index, _, fingerprint = minima[0]
            selected.setdefault(fingerprint.words, fingerprint)
    return selected


def compare(left: str, right: str) -> Comparison:
    left_fingerprints, right_fingerprints = fingerprints(left), fingerprints(right)
    shared = left_fingerprints.keys() & right_fingerprints.keys()
    union_size = len(left_fingerprints) + len(right_fingerprints) - len(shared)
    ordered = sorted(shared, key=lambda words: left_fingerprints[words].start)
    evidence = tuple(
        (left_fingerprints[words], right_fingerprints[words]) for words in ordered[:12]
    )
    return Comparison(
        len(shared) / union_size if union_size else 0.0,
        len(shared),
        len(left_fingerprints),
        len(right_fingerprints),
        evidence,
    )
