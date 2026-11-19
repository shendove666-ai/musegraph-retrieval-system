"""Combine retrieval signals and expose the evidence behind each result."""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from threading import RLock

from . import repository
from .algorithms.fingerprint import fingerprints
from .algorithms.text import scan
from .algorithms.tfidf import Tfidf
from .repository import Document
from .semantic import SemanticIndex, SentenceEncoder

MODES = {
    "hybrid": "Hybrid",
    "lexical": "TF-IDF",
    "fingerprint": "Winnowing",
    "semantic": "Sentence-BERT",
}
HYBRID_WEIGHTS = (0.45, 0.20, 0.35)
FEEDBACK_WEIGHT = 0.15


@dataclass(frozen=True, slots=True)
class SearchHit:
    document: Document
    score: float
    lexical: float
    fingerprint: float
    semantic: float | None
    vote: int
    adjustment: float
    matched_terms: Sequence[str]
    matched_phrase: str
    passage: str


def excerpt(text: str, matched_terms: Sequence[str], width: int = 275) -> str:
    if len(text) <= width:
        return text
    match = next((token for token in scan(text) if token.term in matched_terms), None)
    start = max(0, min(match.start - width // 3, len(text) - width)) if match else 0
    end = min(start + width, len(text))
    return ("…" if start else "") + text[start:end].strip() + ("…" if end < len(text) else "")


class SearchIndex:
    def __init__(self, documents: list[Document], encoder: SentenceEncoder | None = None):
        self.documents = documents
        self.lexical = Tfidf([f"{doc.title} {doc.author} {doc.body}" for doc in documents])
        self.fingerprints = [fingerprints(doc.body) for doc in documents]
        self.encoder = encoder
        self._semantic = None
        self._lock = RLock()

    def prepare_semantic(self) -> SemanticIndex | None:
        if self.encoder is None or not self.documents:
            return None
        with self._lock:
            if self._semantic is None:
                self._semantic = SemanticIndex([doc.body for doc in self.documents], self.encoder)
            return self._semantic

    def rank(
        self, query: str, mode: str = "hybrid", votes: dict[str, int] | None = None
    ) -> list[SearchHit]:
        """Rank all eligible passages by adjusted score, breaking ties by passage ID."""
        if mode not in MODES:
            raise ValueError(f"Unknown retrieval mode: {mode}.")
        if mode == "semantic" and self.encoder is None:
            raise ValueError("Semantic mode is disabled.")
        if not self.documents or not scan(query):
            return []
        votes = votes or {}
        lexical_scores = self.lexical.score(query)
        query_fingerprints = fingerprints(query)
        semantic_scores: list[tuple[float | None, str]] = [(None, "")] * len(self.documents)
        if self.encoder is not None and mode in {"hybrid", "semantic"}:
            semantic_index = self.prepare_semantic()
            if semantic_index is not None:
                semantic_scores = semantic_index.score(query)

        hits = []
        passage_signals = zip(
            self.documents, lexical_scores, self.fingerprints, semantic_scores, strict=True
        )
        for document, (lexical, matched_terms), document_fingerprints, (semantic, passage) in passage_signals:
            shared = document_fingerprints.keys() & query_fingerprints.keys()
            fingerprint = len(shared) / len(query_fingerprints) if query_fingerprints else 0.0
            if mode == "hybrid":
                weights = HYBRID_WEIGHTS if semantic is not None else HYBRID_WEIGHTS[:2]
                signals = (lexical, fingerprint, semantic or 0.0)
                base_score = sum(weight * signal for weight, signal in zip(weights, signals)) / sum(weights)
            else:
                base_score = {"lexical": lexical, "fingerprint": fingerprint, "semantic": semantic}[mode]
            if not base_score:
                continue

            anchor = min(
                (document_fingerprints[fingerprint_key] for fingerprint_key in shared),
                key=lambda fingerprint: fingerprint.start,
                default=None,
            )
            phrase = document.body[anchor.start:anchor.end] if anchor else ""
            vote = votes.get(document.id, 0)
            adjustment = FEEDBACK_WEIGHT * vote
            hits.append(SearchHit(
                document, base_score + adjustment, lexical, fingerprint, semantic, vote,
                adjustment, matched_terms, phrase, passage or excerpt(document.body, matched_terms),
            ))
        return sorted(hits, key=lambda hit: (-hit.score, hit.document.id))


class IndexCache:
    def __init__(self, encoder: SentenceEncoder | None):
        self.encoder = encoder
        self._entry: tuple[int, SearchIndex] | None = None
        self._lock = RLock()

    def get(self, db: sqlite3.Connection) -> SearchIndex:
        """Read revision and passages from the same SQLite snapshot on a cache miss."""
        with self._lock:
            db.execute("BEGIN")
            try:
                revision = repository.revision(db)
                if self._entry is not None and self._entry[0] == revision:
                    return self._entry[1]
                documents = repository.documents(db)
            finally:
                db.rollback()
            index = SearchIndex(documents, self.encoder)
            self._entry = revision, index
            return index
