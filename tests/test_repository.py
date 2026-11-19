"""Verify validated imports, replacement, and revision stability."""

import io
import json
import sqlite3
from contextlib import closing

import pytest

from musegraph import create_app
from musegraph.db import get_db
from musegraph.repository import Document, import_corpus, read_corpus, revision, save_vote, votes_for


def test_repeat_import_and_replacement(app):
    with app.app_context():
        db = get_db()
        passage = Document("meter", "Hymn meter", "Archive", "Eight and six syllables.")
        import_corpus(db, [passage], False)
        before = revision(db)
        import_corpus(db, [passage], False)
        assert revision(db) == before
        save_vote(db, "session", "hymn", "meter", 1)
        import_corpus(db, [passage], True)
        assert revision(db) > before
        assert votes_for(db, "session", "hymn") == {}


def test_invalid_corpus_cannot_replace_existing_records(app, tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('[{"id":"only-an-id"}]', encoding="utf-8")
    runner = app.test_cli_runner()
    cli_result = runner.invoke(args=["load-corpus", str(path), "--replace"])
    assert cli_result.exit_code == 1
    assert "invalid fields" in cli_result.output
    assert "Corpus passages: 3" in runner.invoke(args=["corpus-info"]).output


def test_rejects_unsafe_urls_and_duplicate_ids():
    passage_fields = {"id": "a", "title": "Title", "author": "Author", "body": "Body"}
    for corpus_payload in [[passage_fields, passage_fields], [{**passage_fields, "source_url": "javascript:alert(1)"}]]:
        with pytest.raises(ValueError):
            read_corpus(io.StringIO(json.dumps(corpus_payload)))


def test_init_db_is_idempotent(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["init-db", "--replace"]).exit_code == 0
    with app.app_context():
        before = revision(get_db())
    assert runner.invoke(args=["init-db"]).exit_code == 0
    with app.app_context():
        assert revision(get_db()) == before
    assert "Corpus passages: 2,286" in runner.invoke(args=["corpus-info"]).output


def test_fresh_app_uses_bundled_corpus_and_preserves_custom_import(tmp_path):
    config = {"TESTING": True, "DATABASE": tmp_path / "fresh.sqlite3"}
    app = create_app(config)
    client = app.test_client()
    assert b"2286 indexed passages" in client.get("/").data
    passage = client.get("/document/pg18444-0040")
    assert b"Meyer Lyon" in passage.data
    assert b"Edition file SHA-256" in passage.data
    assert b"Passage SHA-256" in passage.data
    with app.app_context():
        import_corpus(get_db(), [Document("custom", "Custom entry", "Archive", "A single entry.")], True)
    restarted = create_app(config)
    assert b"1 indexed passages" in restarted.test_client().get("/").data


def test_startup_removes_retired_rows_and_keeps_existing_imports(tmp_path):
    config = {"TESTING": True, "DATABASE": tmp_path / "upgrade.sqlite3"}
    old_app = create_app({**config, "AUTOLOAD_CORPUS": False})
    with old_app.app_context():
        import_corpus(get_db(), [
            Document(
                "sonata-exposition", "Tonal motion in the sonata exposition", "Mao Wen",
                "In a major-key sonata exposition, the opening theme establishes the tonic before "
                "a transition leads toward the dominant. A secondary theme may introduce a new "
                "texture, but the decisive change is tonal. A cadence in the new key confirms the "
                "move away from the opening tonal center.",
            ),
            Document("custom", "Custom entry", "Archive", "A single entry."),
        ], False)
    client = create_app(config).test_client()
    assert client.get("/document/sonata-exposition").status_code == 404
    assert client.get("/document/custom").status_code == 200
    assert client.get("/document/pg18444-0040").status_code == 200


def test_legacy_table_adds_hash_columns_and_preserves_passage(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.executescript(
            """
            CREATE TABLE documents (
                id TEXT PRIMARY KEY NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                body TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                locator TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO documents (id, title, author, body)
            VALUES ('legacy', 'Legacy title', 'Archive', 'An existing passage.');
            """
        )

    app = create_app({"TESTING": True, "DATABASE": database, "AUTOLOAD_CORPUS": False})
    with app.app_context():
        db = get_db()
        row = db.execute("SELECT body, source_sha256, passage_sha256 FROM documents").fetchone()
        assert tuple(row) == ("An existing passage.", "", "")
    assert b"An existing passage." in app.test_client().get("/document/legacy").data
