"""Load and inspect a MuseGraph corpus from the command line."""

import click
from flask import Flask
from flask.cli import with_appcontext

from .benchmark import evaluate_command
from .db import get_db
from .initialization import load_default
from .repository import import_corpus, read_corpus


@click.command("load-corpus")
@click.argument("path", type=click.File("r", encoding="utf-8"))
@click.option("--replace", is_flag=True, help="Replace the corpus and clear its votes.")
@with_appcontext
def load_corpus(path, replace: bool) -> None:
    """Import passage records from a JSON file."""
    try:
        records = read_corpus(path)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    import_corpus(get_db(), records, replace)
    click.echo(f"Loaded {len(records):,} passages.")


@click.command("init-db")
@click.option("--replace", is_flag=True, help="Replace the corpus and clear its votes.")
@with_appcontext
def init_db(replace: bool) -> None:
    """Initialize the database with the bundled Gutenberg passages."""
    db = get_db()
    with db:
        count = load_default(db, replace)
    click.echo(f"Loaded {count:,} Gutenberg passages.")


@click.command("corpus-info")
@with_appcontext
def corpus_info() -> None:
    """Print the number of indexed passages."""
    count = get_db().execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    click.echo(f"Corpus passages: {count:,}")


def register(app: Flask) -> None:
    app.cli.add_command(evaluate_command)
    app.cli.add_command(load_corpus)
    app.cli.add_command(init_db)
    app.cli.add_command(corpus_info)
