# Benchmark results

**Mao Wen**

I compare TF-IDF, Winnowing, Sentence-BERT, and Hybrid on the same 2,286 passages and ten graded queries, with feedback disabled. This is a single-annotator pilot benchmark. The benchmark averages query scores at rank five, and the two commands use the same evaluator and inputs. [Judgment set](data/real_judgments.json) · [Evaluation protocol](TECHNICAL_REPORT.md#evaluation)

| Mode | Precision@5 | Recall@5 | nDCG@5 | `evaluate` median | `analyze_errors.py` median |
| --- | ---: | ---: | ---: | ---: | ---: |
| TF-IDF | 0.5000 | 0.7456 | 0.8417 | 836.34 ms | 1080.82 ms |
| Winnowing | 0.0800 | 0.4000 | 0.4000 | 17.38 ms | 17.04 ms |
| Sentence-BERT | 0.4000 | 0.4011 | 0.4209 | 52.08 ms | 59.22 ms |
| **Hybrid with Sentence-BERT** | 0.5800 | 0.8125 | 0.8949 | 56.39 ms | 58.06 ms |

Winnowing ranked the exact passage first for all four quotation queries. That category’s Precision@5 was 0.2000 because each query had one positive, and the metric divides by five. On the three paraphrases, Hybrid reached 0.7269 nDCG@5, compared with 0.6735 for TF-IDF and 0.4373 for Sentence-BERT. The known positives in the judgment file determine recall for the term and paraphrase queries. [Examples and missed passages](ERROR_ANALYSIS.md)

## Timing

I ran both commands on Windows with an Intel Core i7-7700HQ, Python 3.13.17, Sentence Transformers 5.7.0, and PyTorch 2.15.0+cpu. I set `OMP_NUM_THREADS=4` and used the pinned MiniLM revision from the local model cache. These are timings from two offline runs using the model ID and pinned revision. The first run overlapped the integration suite, so process load differed across the two runs.

| Entry point | Sparse setup | Dense setup | End to end |
| --- | ---: | ---: | ---: |
| `evaluate` | 4.04 s | 311.40 s | 324.08 s |
| `analyze_errors.py` | 3.60 s | 239.03 s | 254.11 s |

I include corpus and judgment loading plus sparse index construction in sparse setup. Dense setup includes loading the model and encoding the corpus. Query latency includes ranking and evidence selection. End-to-end timing stops after assembling the report, before writing JSON. TF-IDF searches the original passage body for excerpts, while the dense modes can reuse the selected window. The timings reflect that difference in work as well as scoring.

## Reproduce the benchmark

With the semantic extra installed, run the following from the repository root.

```bash
python -m musegraph evaluate --semantic --k 5 --output data/generated/evaluation.json
python -m scripts.analyze_errors --semantic --k 5 --output data/generated/errors.json
```

I retain the input hashes, model revision, per-query rankings, relevance grades, missed positives, and timings in the saved reports. [Evaluation output](data/real_evaluation.json) · [Error analysis output](data/real_error_analysis.json)
