# Gutenberg corpus and evaluation data

**Mao Wen**

I use the same **2,286 passages from five Project Gutenberg books** for the browser and the benchmark. Flask startup, `init-db`, `evaluate`, and `analyze_errors.py` all default to [real_documents.json](real_documents.json). Its SHA-256 is `993afaf0a5652b264e2422d33a3c56ab87282987b0205ca4595960418b3c8857`. [Edition license](GUTENBERG_LICENSE.txt)

## Source editions

| Edition | Work | Author | Passages | Edition SHA-256 |
| --- | --- | --- | ---: | --- |
| [5724](https://www.gutenberg.org/ebooks/5724) | A Book of Operas | Henry Edward Krehbiel | 463 | `1ab929affba551cfe0bd65228c0cb2fe53b26ef6329748802d7f80d7f8867d23` |
| [17474](https://www.gutenberg.org/ebooks/17474) | How to Listen to Music, 7th ed. | Henry Edward Krehbiel | 345 | `b47a4fea80fc3e1f6a03bd0b66906d730d6a52e6d80962eb9b2aaa5c3e30a4aa` |
| [18444](https://www.gutenberg.org/ebooks/18444) | The Story of the Hymns and Tunes | Theron Brown and Hezekiah Butterworth | 681 | `838054f56d6c96b56ec19dd7069b972f290eecfae1f9623e41747dc217cea40b` |
| [28056](https://www.gutenberg.org/ebooks/28056) | Music and Some Highly Musical People | James Monroe Trotter | 555 | `ab9523c95083980c02282776def4073a87c0f39729b01906c13c176b6ee947ad` |
| [70203](https://www.gutenberg.org/ebooks/70203) | The Story of Chamber Music | Nicholas Kilburn | 242 | `566941a4c358c49ee77396ffdcdcb63609b29e93fa1f2e006dad6e831231f1cc` |

The builder reads UTF-8 text between the edition markers and takes successive blocks of 180 words, using whitespace for token boundaries. I keep the shorter last block, as well as contents pages and indexes within the marked text. The word range is inclusive and counts from the start of that text. The edition digest covers the original file bytes. The passage digest covers the stored UTF-8 body after whitespace is collapsed.

## Rebuild

I use the following command from the repository root to recreate the complete collection in a separate file. The builder includes every successive block between each edition's Project Gutenberg start and end markers.

```bash
python scripts/build_real_corpus.py --output data/generated/gutenberg.json
```

The offline rebuild check reproduces the bundled JSON byte for byte from the five cached editions. The builder stores edition files in `data/cache` by numeric book ID with a `.txt` suffix. Add `--offline` to rebuild from that cache. I compare the edition digests before comparing outputs because upstream revisions or a different `--words` setting can change passage boundaries. [Builder and download sources](../scripts/build_real_corpus.py)

## Judgment format

I include ten benchmark queries in [real_judgments.json](real_judgments.json), with three term queries, three paraphrases, and four quotations. Each record has an ID, query string, category, and a mapping from passage IDs to integer grades. The stored grades assign 0 to reviewed nonrelevance, 1 to useful context, 2 to substantial coverage, and 3 to a direct answer. Quotation positives contain the full normalized query sequence. Term and paraphrase judgments cover a pool of candidate passages. Unjudged passages contribute zero gain and retain `judged: false` in the reports.

For a custom evaluation, pass both `--corpus` and `--judgments`. Each corpus row requires `id`, `title`, `author`, and `body`. Edition URL, locator, and digests are optional for custom rows. I validate any supplied passage digest against the imported body. [Evaluation protocol](../TECHNICAL_REPORT.md) · [Measured results](../RESULTS.md)
