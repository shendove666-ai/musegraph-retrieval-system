"""Manage request-local SQLite connections and the installed schema."""

import sqlite3
from importlib.resources import files

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    connection = get_db()
    connection.executescript(files("musegraph").joinpath("schema.sql").read_text(encoding="utf-8"))
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(documents)")}
        for name in ("source_sha256", "passage_sha256"):
            if name not in columns:
                connection.execute(f"ALTER TABLE documents ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
