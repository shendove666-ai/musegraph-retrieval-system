# Changelog

**Mao Wen**

## 1.2.0 · Complete Gutenberg corpus

- Restored four source passages that had no corpus-level exclusion criterion.
- Rebuilt the bundled collection from all text between the Project Gutenberg edition markers, producing 2,286 passages from five books.
- Re-ran both benchmark entry points on the complete collection and refreshed the saved reports and documentation.
- Updated the corpus assertions in the automated tests; all 24 tests pass with the semantic integration test enabled.
- Clarified the scope of the ten-query, single-annotator pilot benchmark.

## 1.1.1 · Initial public release

Version 1.1.1 was the first public GitHub release of a project developed and tested locally before repository publication. It included:

- Custom TF-IDF and Winnowing implementations, optional Sentence-BERT retrieval, and Hybrid ranking.
- Passage comparison, query history, source verification, and session-scoped relevance feedback.
- A bundled Project Gutenberg collection, graded retrieval queries, saved reports, automated tests, screenshots, and a local demonstration video.
