"""Exercise corpus construction and error reporting through their CLI entry points."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from musegraph.benchmark import _write_report

ROOT = Path(__file__).resolve().parents[1]


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *map(str, args)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"},
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def test_corpus_builder_reuses_cache_and_keeps_last_passage(tmp_path):
    text = " ".join(f"word{i}" for i in range(43))
    source = tmp_path / "17474.txt"
    source.write_text(
        f"Header\n*** START OF THE PROJECT GUTENBERG EBOOK TITLE ***\n{text}\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK TITLE ***\nFooter\n",
        encoding="utf-8-sig",
    )
    output = tmp_path / "corpus.json"
    args = ("--offline", "--book", 17474, "--words", 40, "--cache", tmp_path, "--output", output)
    cli_result = run_script("build_real_corpus.py", *args)
    assert cli_result.returncode == 0, cli_result.stderr
    records = json.loads(output.read_text(encoding="utf-8"))
    assert [row["id"] for row in records] == ["pg17474-0001", "pg17474-0002"]
    assert records[1]["body"] == "word40 word41 word42"
    assert records[1]["locator"] == "Words 41–43"
    assert len(records[1]["source_sha256"]) == len(records[1]["passage_sha256"]) == 64
    source.write_text("Incomplete download", encoding="utf-8")
    assert run_script("build_real_corpus.py", *args).returncode == 1
    assert json.loads(output.read_text(encoding="utf-8")) == records


def test_error_report_retains_signal_breakdown(tmp_path):
    output = tmp_path / "report.json"
    cli_result = run_script("analyze_errors.py", "--mode", "lexical", "--k", 3, "--output", output)
    assert cli_result.returncode == 0, cli_result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passage_count"] == 2286
    lexical, = report["reports"]
    assert lexical["query_count"] == 10
    assert lexical["k"] == 3
    first_query, *remaining_queries = lexical["queries"]
    assert first_query["ranked"][0]["id"].startswith("pg")
    assert first_query["ranked"][0]["lexical"] > 0
    assert any(query["missing_relevant"] for query in remaining_queries)
    assert lexical["timing"]["median_query_ms"] > 0


def test_report_replace_failure_preserves_previous_json(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    output.write_bytes(b'{"previous": true}\n')

    def fail_replace(_staged, _target):
        raise OSError("replacement failed")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="replacement failed"):
        _write_report(output, {"previous": False})

    assert output.read_bytes() == b'{"previous": true}\n'
    assert list(tmp_path.iterdir()) == [output]
