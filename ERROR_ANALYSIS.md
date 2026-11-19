# Retrieval error analysis

**Mao Wen**

I use three queries to inspect the differences between a good score and a passage that answers the query. Each case can be traced through the stored query, grades, and ranked passage IDs. [Query-level output](data/real_error_analysis.json)

In the ten-query error-analysis run, Hybrid with Sentence-BERT reached **0.5800 Precision@5**, **0.8125 Recall@5**, and **0.8949 nDCG@5**. Its median retrieval time after setup was **58.06 ms**. The full benchmark took **254.11 s**. The run is a single-annotator pilot evaluation over this collection.

## R05 · Wagner’s recurring dramatic themes

The judgments assign the highest grade to `pg17474-0249`, where Krehbiel describes how Wagner’s recurring musical phrases represent characters and other dramatic agencies. All four modes leave it outside the top five. Sentence-BERT and Hybrid put `pg5724-0307` first. That passage discusses recurring themes, with an emphasis on the limits of treating them as a catalog. I would try including the historical phrase “typical phrases” in a separate query to see whether vocabulary accounts for the miss.

## R06 · New York Philharmonic seating

TF-IDF and Hybrid rank `pg17474-0076` first, which introduces the seating plan. Sentence-BERT puts `pg17474-0081` first, where the orchestra and the instrument names occur in a table of section sizes. Hybrid ranks `pg17474-0077` third. That passage gives the actual stage positions. I include this case because the top semantic result shares nearly all of the topic vocabulary and still leaves the spatial question unanswered.

## R08 · The Leoni quotation

The query appears in full in `pg18444-0041`. Winnowing, TF-IDF, and Hybrid rank it first. Sentence-BERT places the neighboring `pg18444-0040` first and leaves the exact quotation outside the top five. Both passages discuss the tune and the singer. I keep the shared phrase visible in the result so readers can verify the wording directly. [Browser walkthrough](DEMO.md)

## Inspect another query

I start with `reports[].queries[]` in the JSON. Each row records the ranked passage IDs, grades, score components, evidence, retrieval time, and known positives outside the cutoff. A row marked `judged: false` has no grade annotation and contributes zero in the metric calculation. In the running app, `/document/<id>` opens the source passage for any listed ID. [Judgment format](data/README.md#judgment-format) · [Metric summary](RESULTS.md)
