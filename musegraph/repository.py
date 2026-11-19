"""Persist corpus records, search history, and explicit votes."""

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import TextIO
from urllib.parse import urlsplit

from .algorithms.text import terms

DOCUMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")
BODY_LIMIT = 100_000
SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    title: str
    author: str
    body: str
    source_url: str = ""
    locator: str = ""
    source_sha256: str = ""
    passage_sha256: str = ""


def read_corpus(stream: TextIO) -> list[Document]:
    corpus_payload = json.load(stream)
    if not isinstance(corpus_payload, list) or not corpus_payload:
        raise ValueError("A corpus must be a nonempty JSON array.")
    passage_records = []
    seen_document_ids = set()
    required = {"id", "title", "author", "body"}
    allowed = required | {"source_url", "locator", "source_sha256", "passage_sha256"}
    for record_number, passage_fields in enumerate(corpus_payload, start=1):
        if (
            not isinstance(passage_fields, dict)
            or not required <= passage_fields.keys() <= allowed
            or any(not isinstance(value, str) for value in passage_fields.values())
        ):
            raise ValueError(f"Corpus record {record_number} has invalid fields.")
        document = Document(**{name: value.strip() for name, value in passage_fields.items()})
        if not DOCUMENT_ID.fullmatch(document.id) or document.id in seen_document_ids:
            raise ValueError(f"Corpus record {record_number} has an invalid or repeated ID.")
        if not document.title or not document.author or not document.body:
            raise ValueError(f"Corpus record {record_number} requires a title, author, and body.")
        if len(document.body) > BODY_LIMIT:
            raise ValueError(f"Corpus record {record_number} exceeds {BODY_LIMIT:,} characters.")
        if document.source_url:
            url = urlsplit(document.source_url)
            if url.scheme not in {"http", "https"} or not url.hostname:
                raise ValueError(f"Corpus record {record_number} has an invalid source URL.")
        for digest in (document.source_sha256, document.passage_sha256):
            if digest and not SHA256.fullmatch(digest):
                raise ValueError(f"Corpus record {record_number} has an invalid SHA-256 digest.")
        if (
            document.passage_sha256
            and sha256(document.body.encode("utf-8")).hexdigest() != document.passage_sha256
        ):
            raise ValueError(f"Corpus record {record_number} does not match its passage SHA-256 digest.")
        passage_records.append(document)
        seen_document_ids.add(document.id)
    return passage_records


def write_corpus(db: sqlite3.Connection, records: list[Document], replace: bool) -> None:
    """Write validated passages within the caller's transaction."""
    if replace:
        db.execute("DELETE FROM documents")
    db.executemany(
        """
        INSERT INTO documents (id, title, author, body, source_url, locator, source_sha256, passage_sha256)
        VALUES (:id, :title, :author, :body, :source_url, :locator, :source_sha256, :passage_sha256)
        ON CONFLICT(id) DO UPDATE SET title = excluded.title, author = excluded.author,
            body = excluded.body, source_url = excluded.source_url, locator = excluded.locator,
            source_sha256 = excluded.source_sha256, passage_sha256 = excluded.passage_sha256
        WHERE (documents.title, documents.author, documents.body,
               documents.source_url, documents.locator, documents.source_sha256, documents.passage_sha256)
            IS NOT (excluded.title, excluded.author, excluded.body,
                    excluded.source_url, excluded.locator, excluded.source_sha256, excluded.passage_sha256)
        """,
        (asdict(record) for record in records),
    )


def import_corpus(db: sqlite3.Connection, records: list[Document], replace: bool) -> None:
    with db:
        write_corpus(db, records, replace)


def documents(db: sqlite3.Connection) -> list[Document]:
    passage_rows = db.execute(
        """
        SELECT id, title, author, body, source_url, locator, source_sha256, passage_sha256
        FROM documents ORDER BY id
        """
    )
    return [Document(**dict(passage_row)) for passage_row in passage_rows]


def get_document(db: sqlite3.Connection, document_id: str) -> Document | None:
    passage_row = db.execute(
        """
        SELECT id, title, author, body, source_url, locator, source_sha256, passage_sha256
        FROM documents WHERE id = ?
        """,
        (document_id,),
    ).fetchone()
    return Document(**dict(passage_row)) if passage_row else None


def revision(db: sqlite3.Connection) -> int:
    return db.execute("SELECT revision FROM corpus_revision WHERE singleton = 1").fetchone()[0]


def query_key(query: str) -> str:
    return " ".join(terms(query))


def record_search(db: sqlite3.Connection, session_id: str, query: str, mode: str) -> None:
    with db:
        db.execute(
            """
            INSERT INTO history VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id, query_key, mode)
            DO UPDATE SET query = excluded.query, searched_at = excluded.searched_at
            """,
            (session_id, query_key(query), query, mode, datetime.now(UTC).isoformat()),
        )


def get_history(db: sqlite3.Connection, session_id: str) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT query, mode, searched_at FROM history WHERE session_id = ?
        ORDER BY searched_at DESC, query_key, mode LIMIT 50
        """,
        (session_id,),
    ).fetchall()


def votes_for(db: sqlite3.Connection, session_id: str, query: str) -> dict[str, int]:
    return dict(db.execute(
        "SELECT document_id, vote FROM feedback WHERE session_id = ? AND query_key = ?",
        (session_id, query_key(query)),
    ))


def save_vote(
    db: sqlite3.Connection, session_id: str, query: str, document_id: str, vote: int
) -> None:
    vote_key = (session_id, query_key(query), document_id)
    with db:
        if vote == 0:
            db.execute(
                "DELETE FROM feedback WHERE session_id = ? AND query_key = ? AND document_id = ?",
                vote_key,
            )
        else:
            db.execute(
                """
                INSERT INTO feedback VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, query_key, document_id) DO UPDATE SET vote = excluded.vote
                """,
                (*vote_key, vote),
            )


def clear_session(db: sqlite3.Connection, session_id: str) -> None:
    with db:
        db.execute("DELETE FROM history WHERE session_id = ?", (session_id,))
        db.execute("DELETE FROM feedback WHERE session_id = ?", (session_id,))
