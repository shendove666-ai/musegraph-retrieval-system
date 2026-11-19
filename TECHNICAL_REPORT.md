# MuseGraph technical report

**Mao Wen**

I built MuseGraph to find named people and works, recover arguments I remember in my own words, and locate quotations in music literature. I index 2,286 passages from five Project Gutenberg books and keep the edition and word range available at every result. [Corpus inventory](data/README.md)

## Lexical evidence

I count terms across title, author, and passage body. I normalize tokens with Unicode NFKC, case folding, and apostrophe normalization. For term frequency `tf`, document frequency `df`, and `N` passage records, the weight is `(1 + ln(tf)) × (1 + ln((1 + N) / (1 + df)))`. I normalize both the query and passage vectors to unit length, so their dot product is cosine similarity. Each result can show up to eight shared terms, ordered by contribution to the dot product. [TF-IDF implementation](musegraph/algorithms/tfidf.py)

## Local fingerprints

I hash consecutive five-word tuples with 64-bit BLAKE2b and select the rightmost minimum in each window of four hashes. Two passages with a shared run of eight normalized words share a complete selection window. Inputs with five to seven words use a shorter window. An input with fewer than five words has no fingerprint. I key matches by the normalized tuples themselves. Tuple equality verifies every reported match, including when hashes collide.

In search, I divide the number of shared distinct fingerprints by the number in the query. In Compare, I divide the same intersection size by the union size to obtain Jaccard similarity. I retain the first occurrence of each selected tuple and use those character ranges to highlight both texts. [Winnowing paper](https://sschleimer.warwick.ac.uk/Maths/winnowing.pdf) · [Fingerprint code](musegraph/algorithms/fingerprint.py)

## Semantic evidence and fusion

I use the pretrained `sentence-transformers/all-MiniLM-L6-v2` checkpoint at a pinned revision. I split passage bodies into windows of up to 128 model tokens with up to 24 tokens of overlap. I normalize window and query embeddings to unit length, take the highest window cosine for each passage, clip it to [0, 1], and show that window’s original text. The model’s input limit still applies to the query. [Sentence-BERT paper](https://aclanthology.org/D19-1410/) · [Pinned checkpoint](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/c9745ed1d9f207416be6d2e6f8de32d1f16199bf)

I combine lexical, fingerprint, and semantic scores with weights of 0.45, 0.20, and 0.35. With the encoder disabled, I divide the two remaining weights by 0.65. A passage must have a positive base score to enter the result list. A Relevant or Off topic vote adds or subtracts 0.15 for the current session and normalized query. Equal scores break by passage ID. A final score can fall outside [0, 1] after feedback. [Ranking code](musegraph/ranking.py)

## Algorithm costs

For a fixed five-word gram, I generate fingerprints in linear time in the number of input tokens, assuming bounded per-token hashing cost. Each hash enters and leaves the monotonic deque at most once. The deque keeps at most four candidates, while the token spans and stored fingerprint tuples grow with the input. Compare performs set operations on the selected tuples, then orders the shared spans by their first occurrence.

Each request scans the passage collection. For `N` passages and `Q` distinct weighted query terms, lexical dot products make up to `N × Q` dictionary lookups before evidence preparation. Dense scoring takes a dot product for each stored window, with cost proportional to the window count times the embedding dimension after query encoding. The ranker sorts all passages with a positive base score, at most `O(N log N)`. The current implementation keeps vectors and fingerprints in memory, and rebuilds the dense index when a worker starts using it or the corpus changes.

## Evaluation

I compare four ranking modes on the same ten queries at rank five, with session feedback disabled. This single-annotator pilot benchmark includes three term searches, three paraphrases, and four quotations. The stored judgments for terms and paraphrases cover pooled retrieval candidates and nearby passages. For quotations the positive criterion is the full normalized query sequence. An unjudged passage contributes zero gain. Recall therefore measures recovery of known positives.

I macro-average Precision@5, Recall@5, and nDCG@5 over the ten queries. Precision uses five slots even when the ranker returns fewer hits. Recall divides by the number of known positives. nDCG uses graded gain `2^grade − 1`, discount `log2(rank + 1)`, and normalization against the ideal order of the known grades.

Hybrid with Sentence-BERT reached **0.5800 Precision@5**, **0.8125 Recall@5**, and **0.8949 nDCG@5**. Ranking and evidence selection took a median of **56.39 ms** in `evaluate` and **58.06 ms** in `analyze_errors.py` after index setup. The end-to-end runs took **324.08 s** and **254.11 s**, respectively.

I would evaluate more independently graded queries before tuning fusion weights or making comparisons across collections. To understand the behavior of the existing system, I inspect the missing direct answers and the passages that displaced them. [Full results and timings](RESULTS.md) · [Error analysis](ERROR_ANALYSIS.md)
