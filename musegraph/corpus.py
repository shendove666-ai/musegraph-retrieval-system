"""Locate the versioned Gutenberg resources in a checkout or installation."""

from importlib.resources import files
from pathlib import Path


def resource_path(name: str):
    checkout = Path(__file__).resolve().parents[1] / "data" / name
    if checkout.is_file():
        return checkout
    return files("musegraph.data").joinpath(name)


def default_corpus() -> bytes:
    return resource_path("real_documents.json").read_bytes()


def default_judgments() -> bytes:
    return resource_path("real_judgments.json").read_bytes()
