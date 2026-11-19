# Retrieval methodology

This document connects each retrieval claim to the implementation. It focuses on the calculations and the evidence returned to the browser. The experiment protocol is documented separately in [experiments.md](experiments.md).

## Text normalization

`musegraph/algorithms/text.py` scans alphanumeric words while retaining their original half-open character spans. It applies Unicode NFKC normalization, case folding, and apostrophe normalization. The retained spans allow a normalized match to be highlighted in the source text.

## TF-IDF

`musegraph/algorithms/tfidf.py` fits one vector per passage record, using the concatenated title, author, and body. For term frequency `tf`, document frequency `df`, and `N` records, it assigns

```text
(1 + ln(tf)) × (1 + ln((1 + N) / (1 + df)))
```

The query and passage vectors are L2 normalized. Their dot product is therefore cosine similarity. The implementation retains the terms with the largest individual contributions and returns the eight strongest terms as result evidence.

For `N` records and `Q` distinct weighted query terms, scoring performs at most `N × Q` passage-vector lookups before evidence preparation. The vectors are stored in memory.

## Winnowing

`musegraph/algorithms/fingerprint.py` forms consecutive five-word tuples. It hashes each tuple with a 64-bit BLAKE2b digest and uses a monotonic deque to select the rightmost minimum from each window of four hashes. Inputs of five to seven words use the available shorter window. Inputs below five words have no fingerprint.

The selected dictionary is keyed by the normalized word tuple itself. Tuple equality therefore verifies each reported match even if two hashes collide. The stored `start` and `end` offsets point back to the original text.

Search divides the number of distinct query fingerprints shared with a passage by the number of distinct query fingerprints. Compare uses

```text
shared fingerprints / union of both fingerprint sets
```

to produce Jaccard similarity.

For fixed gram and window sizes, fingerprint generation is linear in the number of tokens. Every digest enters and leaves the deque at most once. Compare performs set intersection and union over the selected tuples, then orders the displayed matches by their position in the first input.

## Sentence-BERT

`musegraph/semantic.py` loads `sentence-transformers/all-MiniLM-L6-v2` at revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`. It uses the model tokenizer to divide a passage into windows of at most 128 model tokens, with up to 24 overlapping tokens. Each window retains its original text.

The encoder L2 normalizes the query and window embeddings. The semantic score for a passage is the highest query-window cosine, clipped to `[0, 1]`. The corresponding original window is returned as evidence.

Dense scoring computes a dot product for every stored window. After query encoding, its cost is proportional to the number of windows multiplied by the embedding dimension. The dense index is built lazily for the current corpus snapshot. A corpus revision change causes the process to build a new sparse index and discard the old dense index.

## Hybrid fusion

`musegraph/ranking.py` combines the three signals as

```text
0.45 × TF-IDF + 0.20 × Winnowing + 0.35 × Sentence-BERT
```

When semantic retrieval is disabled, Hybrid divides the TF-IDF and Winnowing weights by their sum, `0.65`. If the configured model fails to load or encode with `SemanticUnavailable`, the web search returns 503 and offers a separate TF-IDF search. A passage enters the results only when its base score is positive. Results are ordered by descending score and then by passage ID.

The ranker scans all passages and sorts every positive result, so the final ordering costs at most `O(N log N)` in addition to signal scoring.

## Session feedback

The browser records one vote for each session, normalized query, and passage. A Relevant vote adds `0.15`, and an Off topic vote subtracts `0.15`. Clearing a vote restores the base score. Feedback changes the current session’s ranking and is excluded from the benchmark.

## Source traceability

Each default corpus record includes a Project Gutenberg edition URL, an inclusive word range, the SHA-256 of the downloaded edition bytes, and the SHA-256 of the stored passage body. `musegraph/repository.py` validates supplied passage hashes during import. The source page exposes these fields and links directly to the edition.

## Implementation map

| Claim | Primary implementation |
| --- | --- |
| Unicode normalization and source spans | `musegraph/algorithms/text.py` |
| TF-IDF weighting and evidence terms | `musegraph/algorithms/tfidf.py` |
| Winnowing and Jaccard comparison | `musegraph/algorithms/fingerprint.py` |
| Dense windows and cosine scoring | `musegraph/semantic.py` |
| Hybrid weights and feedback | `musegraph/ranking.py` |
| Metric definitions | `musegraph/evaluation.py` |
| Source hash validation | `musegraph/repository.py` |
