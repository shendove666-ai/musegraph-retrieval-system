# Experimental protocol

This document defines the benchmark inputs, metrics, and timing boundaries used for the committed reports. The complete numbers are in [../RESULTS.md](../RESULTS.md), and individual misses are discussed in [../ERROR_ANALYSIS.md](../ERROR_ANALYSIS.md).

## Retrieval task

The benchmark searches the bundled collection of 2,286 passages. It contains ten queries:

- Three term queries built around names, institutions, or concrete entities.
- Three paraphrase queries describing an information need in different wording.
- Four quotation queries containing remembered source wording.

All modes use the same passage records, query strings, graded judgments, cutoff `k = 5`, and disabled session feedback.

## Relevance judgments

`data/real_judgments.json` maps passage IDs to integer grades:

| Grade | Interpretation |
| ---: | --- |
| 0 | Reviewed and not relevant |
| 1 | Useful context |
| 2 | Substantial coverage |
| 3 | Direct answer |

Quotation positives contain the full normalized sequence. The term and paraphrase judgments cover a pool of candidate passages and nearby relevant material. They are not exhaustive judgments over all 2,286 passages. An unjudged passage contributes zero gain. Mao Wen assigned the grades as the sole annotator, so this benchmark is a pilot evaluation rather than an independent assessment of general retrieval performance.

## Metrics

`musegraph/evaluation.py` computes one result per query and macro-averages across the ten queries.

- Precision@5 is the number of positively graded passages in the first five ranks divided by five. Missing result slots count as nonrelevant.
- Recall@5 is the number of known positive passages in the first five divided by the number of known positives for that query.
- nDCG@5 uses gain `2^grade − 1`, logarithmic rank discount, and normalization by the ideal ordering of the known grades.

Recall should be read as recall over the known judgment pool. It is not corpus-wide exhaustive recall.

## Compared modes

| CLI mode | Signals used |
| --- | --- |
| `lexical` | TF-IDF |
| `fingerprint` | Winnowing |
| `semantic` | Sentence-BERT |
| `hybrid` | TF-IDF, Winnowing, and Sentence-BERT |

## Timing boundaries

The report separates three kinds of work:

- Sparse setup loads the JSON inputs and builds TF-IDF vectors and fingerprints.
- Dense setup loads the Sentence-BERT checkpoint, creates overlapping windows, and encodes all windows.
- Retrieval time covers ranking and evidence selection for a query after setup.

The end-to-end benchmark timer includes report assembly. It excludes Python startup, JSON output writing, and browser rendering.

## Verified environment

The final reports were created on Windows with:

| Component | Value |
| --- | --- |
| CPU | Intel Core i7-7700HQ |
| Python | 3.13.17 |
| Sentence Transformers | 5.7.0 |
| PyTorch | 2.15.0+cpu |
| OpenMP threads | 4 |
| Model | `sentence-transformers/all-MiniLM-L6-v2` |
| Model revision | `c9745ed1d9f207416be6d2e6f8de32d1f16199bf` |

Latency is machine-dependent. The quality metrics and rankings are determined by the committed corpus, judgments, implementation, and pinned model revision.

## Commands

```powershell
python -m musegraph evaluate --semantic --k 5 --output data/generated/evaluation.json
python -m scripts.analyze_errors --semantic --k 5 --output data/generated/errors.json
```

The two entry points intentionally use the same benchmark implementation. Running both checks that their default inputs and reporting paths remain aligned. Their outputs are repeated timed runs, rather than independent evaluation methodologies.
