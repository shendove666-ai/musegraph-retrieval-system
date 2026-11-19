"""Run the same timed retrieval benchmark from the app CLI and error script."""

import io
import json
import platform
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from shutil import copymode
from tempfile import TemporaryDirectory
from time import perf_counter

import click

from .corpus import default_corpus, default_judgments, resource_path
from .evaluation import evaluate, read_judgments
from .ranking import MODES, SearchIndex
from .repository import read_corpus
from .semantic import DEFAULT_MODEL, SemanticUnavailable, SentenceEncoder


def _write_report(output: Path, payload: dict) -> None:
    """Stage a complete report on the same filesystem before publishing it."""
    target = output.resolve()
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and (not target.is_file() or target.stat().st_nlink > 1):
        # Replacing a special file or one name of a hard link would change its meaning.
        target.write_text(serialized, encoding="utf-8", newline="\n")
        return

    with TemporaryDirectory(dir=target.parent) as staging_directory:
        staged = Path(staging_directory) / target.name
        staged.write_text(serialized, encoding="utf-8", newline="\n")
        if target.exists():
            copymode(target, staged)
        staged.replace(target)


@click.command("evaluate")
@click.option("--corpus", type=click.Path(path_type=Path), help="Use a different passage JSON file.")
@click.option("--judgments", type=click.Path(path_type=Path), help="Use different graded judgments.")
@click.option("--output", type=click.Path(path_type=Path), help="Write the full query-level JSON report.")
@click.option("--mode", type=click.Choice(list(MODES)), multiple=True, help="Repeat to select several modes.")
@click.option("--semantic", is_flag=True, help="Enable Sentence-BERT and semantic hybrid scoring.")
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="Model ID or local model directory.")
@click.option("--revision", help="Select a remote model revision.")
@click.option("--k", type=click.IntRange(min=1), default=5, show_default=True)
@click.pass_context
def evaluate_command(ctx, corpus, judgments, output, mode, semantic, model, revision, k):
    """Measure retrieval quality and latency on the bundled Gutenberg passages."""
    defaults = ctx.find_object(dict) or {}
    output = output or defaults.get("report_path", Path("data/generated/evaluation.json"))
    modes = list(dict.fromkeys(mode or (
        ["lexical", "fingerprint", "semantic", "hybrid"] if semantic
        else ["lexical", "fingerprint", "hybrid"]
    )))
    if "semantic" in modes and not semantic:
        raise click.UsageError("--mode semantic requires --semantic.")
    input_paths = [
        corpus or resource_path("real_documents.json"),
        judgments or resource_path("real_judgments.json"),
    ]
    if output.resolve() in {path.resolve() for path in input_paths if isinstance(path, Path)}:
        raise click.UsageError("--output must differ from both input paths.")

    try:
        started = perf_counter()
        corpus_bytes = corpus.read_bytes() if corpus else default_corpus()
        judgment_bytes = judgments.read_bytes() if judgments else default_judgments()
        passage_records = read_corpus(io.StringIO(corpus_bytes.decode("utf-8")))
        query_cases = read_judgments(
            io.StringIO(judgment_bytes.decode("utf-8")), {passage_record.id for passage_record in passage_records}
        )
        encoder = SentenceEncoder(model, revision) if semantic else None
        search_index = SearchIndex(passage_records, encoder)
        sparse_setup = perf_counter() - started
        dense_setup = None
        if encoder and any(name in {"semantic", "hybrid"} for name in modes):
            dense_started = perf_counter()
            search_index.prepare_semantic()
            dense_setup = perf_counter() - dense_started
        reports = [evaluate(search_index, query_cases, name, k) for name in modes]
        payload = {
            "corpus_sha256": sha256(corpus_bytes).hexdigest(),
            "judgments_sha256": sha256(judgment_bytes).hexdigest(),
            "passage_count": len(passage_records),
            "semantic_model": model if encoder else None,
            "semantic_revision": encoder.revision if encoder else None,
            "environment": {
                "python": platform.python_version(),
                "platform": platform.system(),
                "sentence_transformers": version("sentence-transformers") if dense_setup is not None else None,
                "torch": version("torch") if dense_setup is not None else None,
            },
            "timing": {
                "sparse_setup_seconds": sparse_setup,
                "dense_setup_seconds": dense_setup,
                "benchmark_seconds": perf_counter() - started,
            },
            "reports": reports,
        }
        _write_report(output, payload)
    except (OSError, ValueError, SemanticUnavailable) as error:
        raise click.ClickException(str(error)) from error

    for report in reports:
        macro_metrics = report["macro"]
        timing = report["timing"]
        click.echo(
            f"{report['mode']:11s}  P@{k} {macro_metrics['precision']:.4f}  "
            f"R@{k} {macro_metrics['recall']:.4f}  nDCG@{k} {macro_metrics['ndcg']:.4f}  "
            f"median {timing['median_query_ms']:.2f} ms"
        )
    click.echo(f"Benchmark completed in {payload['timing']['benchmark_seconds']:.2f} s.")
    click.echo(f"Wrote query-level results to {output}.")
