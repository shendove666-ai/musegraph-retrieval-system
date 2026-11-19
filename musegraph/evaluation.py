"""Evaluate ranked passages against graded relevance judgments."""

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from math import log2
from statistics import mean, median
from time import perf_counter
from typing import TextIO

from .algorithms.text import terms
from .ranking import SearchIndex


@dataclass(frozen=True, slots=True)
class QueryCase:
    id: str
    query: str
    category: str
    grades: dict[str, int]


@dataclass(frozen=True, slots=True)
class Metrics:
    precision: float
    recall: float
    ndcg: float


def read_judgments(stream: TextIO, document_ids: set[str]) -> list[QueryCase]:
    judgment_rows = json.load(stream)
    if not isinstance(judgment_rows, list) or not judgment_rows:
        raise ValueError("Judgments must be a nonempty JSON array.")
    cases = []
    seen = set()
    for number, judgment_fields in enumerate(judgment_rows, 1):
        if not isinstance(judgment_fields, dict) or judgment_fields.keys() != {"id", "query", "category", "grades"}:
            raise ValueError(f"Judgment {number} requires id, query, category, and grades.")
        if any(not isinstance(judgment_fields[name], str) or not judgment_fields[name].strip()
               for name in ("id", "query", "category")):
            raise ValueError(f"Judgment {number} has invalid metadata.")
        query_id, query, category = (judgment_fields[name].strip() for name in ("id", "query", "category"))
        if query_id in seen or not terms(query):
            raise ValueError(f"Judgment {number} repeats a query ID or has no searchable words.")
        grades = judgment_fields["grades"]
        if not isinstance(grades, dict) or any(
            doc_id not in document_ids or type(grade) is not int or not 0 <= grade <= 3
            for doc_id, grade in grades.items()
        ):
            raise ValueError(f"Judgment {number} has an unknown document or a grade outside 0–3.")
        cases.append(QueryCase(query_id, query, category, grades))
        seen.add(query_id)
    return cases


def dcg(grades: list[int]) -> float:
    return sum((2**grade - 1) / log2(rank + 1) for rank, grade in enumerate(grades, 1))


def metrics_at_k(ranked: list[str], grades: dict[str, int], k: int) -> Metrics:
    """Treat unjudged documents as zero and unfilled ranks as nonrelevant."""
    if k < 1:
        raise ValueError("K must be positive.")
    retrieved = [grades.get(key, 0) for key in list(dict.fromkeys(ranked))[:k]]
    hits = sum(grade > 0 for grade in retrieved)
    relevant = sum(grade > 0 for grade in grades.values())
    ideal = dcg(sorted(grades.values(), reverse=True)[:k])
    return Metrics(hits / k, hits / relevant if relevant else 0.0,
                   dcg(retrieved) / ideal if ideal else 0.0)


def averages(rows: list[Metrics]) -> dict[str, float]:
    return {
        "precision": mean(query_metrics.precision for query_metrics in rows),
        "recall": mean(query_metrics.recall for query_metrics in rows),
        "ndcg": mean(query_metrics.ndcg for query_metrics in rows),
    }


def evaluate(index: SearchIndex, cases: list[QueryCase], mode: str, k: int) -> dict:
    """Summarize macro metrics and retain inspectable errors for every query."""
    categories = defaultdict(list)
    all_metrics = []
    details = []
    durations = []
    for case in cases:
        started = perf_counter()
        hits = index.rank(case.query, mode)[:k]
        elapsed = perf_counter() - started
        durations.append(elapsed)
        ranked = [hit.document.id for hit in hits]
        metrics = metrics_at_k(ranked, case.grades, k)
        categories[case.category].append(metrics)
        all_metrics.append(metrics)
        details.append({
            "id": case.id,
            "query": case.query,
            "category": case.category,
            "metrics": asdict(metrics),
            "retrieval_ms": elapsed * 1000,
            "missing_relevant": [
                {"id": doc_id, "grade": grade}
                for doc_id, grade in sorted(case.grades.items(), key=lambda row: (-row[1], row[0]))
                if grade > 0 and doc_id not in ranked
            ],
            "ranked": [
                {
                    "id": hit.document.id,
                    "grade": case.grades.get(hit.document.id, 0),
                    "judged": hit.document.id in case.grades,
                    "score": hit.score,
                    "lexical": hit.lexical,
                    "fingerprint": hit.fingerprint,
                    "semantic": hit.semantic,
                    "matched_terms": hit.matched_terms,
                    "matched_phrase": hit.matched_phrase,
                }
                for hit in hits
            ],
        })
    return {
        "mode": mode,
        "k": k,
        "query_count": len(cases),
        "macro": averages(all_metrics),
        "timing": {
            "retrieval_seconds": sum(durations),
            "median_query_ms": median(durations) * 1000,
        },
        "categories": {
            name: {"query_count": len(category_metrics), **averages(category_metrics)}
            for name, category_metrics in sorted(categories.items())
        },
        "queries": details,
    }
