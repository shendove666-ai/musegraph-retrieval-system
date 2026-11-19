# Reproducibility guide

This guide starts from a clean clone and covers the bundled corpus, application, benchmark, tests, and browser media. Commands use Windows PowerShell.

## 1. Create the environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

`requirements.txt` pins the direct dependency versions used for the final verification. Transitive packages are resolved by pip. `pyproject.toml` defines the compatibility ranges for normal package installation.

## 2. Verify the bundled data

The application includes the corpus and judgment files in the installed package. No network request is required to initialize SQLite.

```powershell
python -m musegraph init-db --replace
python -m musegraph corpus-info
```

The second command should print:

```text
Corpus passages: 2,286
```

An existing database with a corpus initialization marker keeps its current passages when the application starts, even if a newer bundled edition is available. Before refreshing such a database, take a SQLite-consistent backup and check for custom passages that use bundled IDs. The import without replacement upserts bundled IDs. The replacement command above is for a fresh or disposable database because it deletes the current passages and their votes.

The committed corpus SHA-256 is:

```text
993afaf0a5652b264e2422d33a3c56ab87282987b0205ca4595960418b3c8857
```

Calculate it locally with:

```powershell
(Get-FileHash data/real_documents.json -Algorithm SHA256).Hash.ToLower()
```

Each row also carries the digest of its passage body. The five edition digests and counts are listed in [../data/README.md](../data/README.md).

## 3. Run the application

```powershell
python -m musegraph run
```

Open <http://127.0.0.1:5000/>. To enable semantic retrieval:

```powershell
$env:MUSEGRAPH_SEMANTIC = "true"
python -m musegraph run
```

If the model is already stored locally, set `MUSEGRAPH_SEMANTIC_MODEL` to that directory. The default model revision is pinned in `musegraph/semantic.py`.

## 4. Reproduce the reports

```powershell
$env:OMP_NUM_THREADS = "4"
python -m musegraph evaluate --semantic --k 5 --output data/generated/evaluation.json
python -m scripts.analyze_errors --semantic --k 5 --output data/generated/errors.json
```

Compare the `corpus_sha256`, `judgments_sha256`, `semantic_revision`, passage count, macro metrics, and per-query passage IDs with the committed reports. Timing values will vary by machine.

## 5. Run the tests

The standard test command runs 27 tests and skips the real-model integration test:

```powershell
python -m pytest -q
```

Run all 28 tests with:

```powershell
$env:MUSEGRAPH_TEST_SEMANTIC = "1"
python -m pytest -q
```

The semantic test loads the real Sentence-BERT checkpoint. It therefore requires the semantic dependencies and accessible model weights.

## 6. Rebuild the corpus

The committed corpus can be used directly. To rebuild it, first allow the builder to download the five Project Gutenberg UTF-8 editions into `data/cache`:

```powershell
python scripts/build_real_corpus.py --output data/generated/gutenberg.json
```

After the edition files are cached, add `--offline` to prevent network access. Compare the edition hashes before comparing the output because upstream file changes can alter passage boundaries.

## 7. Regenerate the screenshots and video

Install the browser once, then run the recording script:

```powershell
python -m playwright install chromium
python scripts/make_demo_video.py
```

The script uses a temporary database, loads the bundled corpus, warms the semantic index, takes five 1440 × 1080 screenshots, and writes an H.264 MP4. With Microsoft Edge installed, use:

```powershell
python -m playwright install ffmpeg
python scripts/make_demo_video.py --browser-channel msedge
```

The generated files replace `demo/frame_0.png` through `demo/frame_4.png` and `demo/musegraph_demo.mp4` after the full workflow succeeds.

## Reproducibility boundaries

- The Gutenberg source files can change upstream. Edition SHA-256 values identify the exact inputs used for the committed corpus.
- Sentence-BERT inference is deterministic for the recorded CPU run, but other library versions or hardware can change floating-point values near ranking ties.
- Wall-clock timings depend on hardware, operating system, process load, and model cache state.
- The graded judgments are part of the repository and should remain fixed when comparing retrieval modes.
