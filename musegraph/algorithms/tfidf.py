"""Fit and query an L2-normalized sparse TF-IDF index."""

from collections import Counter
from collections.abc import Sequence
from math import log, sqrt

from .text import terms


class Tfidf:
    def __init__(self, texts: list[str]):
        passage_term_counts = [Counter(terms(text)) for text in texts]
        document_frequency = Counter(
            term for term_counts in passage_term_counts for term in term_counts
        )
        self.idf = {
            term: 1 + log((1 + len(texts)) / (1 + containing_passages))
            for term, containing_passages in document_frequency.items()
        }
        self.vectors = [self._vector(term_counts) for term_counts in passage_term_counts]

    def _vector(self, count: Counter[str]) -> dict[str, float]:
        weights = {
            term: (1 + log(term_frequency)) * self.idf[term]
            for term, term_frequency in count.items()
            if term in self.idf
        }
        norm = sqrt(sum(weight * weight for weight in weights.values()))
        return {term: weight / norm for term, weight in weights.items()} if norm else {}

    def score(self, query: str) -> list[tuple[float, Sequence[str]]]:
        query_vector = self._vector(Counter(terms(query)))
        passage_scores = []
        for passage_vector in self.vectors:
            contributions = {
                term: weight * passage_vector[term]
                for term, weight in query_vector.items()
                if term in passage_vector
            }
            strongest = sorted(contributions, key=lambda term: (-contributions[term], term))
            passage_scores.append((min(1.0, sum(contributions.values())), tuple(strongest[:8])))
        return passage_scores
