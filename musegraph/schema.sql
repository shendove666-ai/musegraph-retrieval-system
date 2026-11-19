CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    locator TEXT NOT NULL DEFAULT '',
    source_sha256 TEXT NOT NULL DEFAULT '',
    passage_sha256 TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS corpus_revision (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    revision INTEGER NOT NULL
);

INSERT OR IGNORE INTO corpus_revision VALUES (1, 0);

CREATE TRIGGER IF NOT EXISTS documents_added AFTER INSERT ON documents
BEGIN
    UPDATE corpus_revision SET revision = revision + 1;
END;

CREATE TRIGGER IF NOT EXISTS documents_changed AFTER UPDATE ON documents
BEGIN
    UPDATE corpus_revision SET revision = revision + 1;
END;

CREATE TRIGGER IF NOT EXISTS documents_removed AFTER DELETE ON documents
BEGIN
    UPDATE corpus_revision SET revision = revision + 1;
END;

CREATE TABLE IF NOT EXISTS settings (
    name TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history (
    session_id TEXT NOT NULL,
    query_key TEXT NOT NULL,
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    searched_at TEXT NOT NULL,
    PRIMARY KEY (session_id, query_key, mode)
);

CREATE TABLE IF NOT EXISTS feedback (
    session_id TEXT NOT NULL,
    query_key TEXT NOT NULL,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    vote INTEGER NOT NULL CHECK (vote IN (-1, 1)),
    PRIMARY KEY (session_id, query_key, document_id)
);

CREATE INDEX IF NOT EXISTS history_recent_by_session
    ON history (session_id, searched_at DESC, query_key, mode);

CREATE INDEX IF NOT EXISTS feedback_by_document
    ON feedback (document_id);
