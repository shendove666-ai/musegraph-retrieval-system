#!/usr/bin/env python3
"""Write the timed Gutenberg benchmark with passage-level errors."""

from pathlib import Path

from musegraph.benchmark import evaluate_command


if __name__ == "__main__":
    evaluate_command.main(
        prog_name="analyze_errors.py", obj={"report_path": Path("data/generated/errors.json")}
    )
