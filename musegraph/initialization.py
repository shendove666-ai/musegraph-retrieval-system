"""Load the bundled corpus once and upgrade databases created by version 1.0."""

import io
import sqlite3
from hashlib import sha256

from .corpus import default_corpus
from .repository import read_corpus, write_corpus

INITIALIZED = "corpus_initialized"

# Row fingerprints identify the retired 1.0 seed records without bundling their text.
RETIRED_ROWS = frozenset({
    "b29157c1a5e5848c8c608520a1aad32bd7b07b8348ef9083ab8990bc84ba27d9",
    "1e9cb37adae3dd6b20e11a45918641cf615de809cbf97e31d8041cff999c51c0",
    "430f4c52f9c8a71f2f8d57b1209c0ff717cfe297c869cc403e51cb92f4861b42",
    "85e725cf351d16dfef65e264791536721fecacc4d2c0ed6ff35d5c534cd0b064",
    "cb6135243f073e56ac823bbf106bbf59550827315fb96484c7b93102b32111f4",
    "326aab24a5092d15961bb5a7847b9eed265b6b5c84917ad8cd9e1a6488cc6175",
    "dff5ca1081ab8a3d9898bfeac83213aaa6a5956fe10ce0daf0fa673bf010e1c6",
    "eebd5470f5b795b43b23626d6ec715682c6dda7550a88dae13b2928cf2400588",
    "f920ccda70964af61426558d98db3d109feaea9f2168a472e755da9a8c0ddbf8",
    "29f7f28465e7e9c40e72b2fb5bbd83685a0ebd072e61e934eeb05a28406dfd13",
    "474be82258fe8a29689374b4d3004eb0be0f44fe8a0408d1c2dee93405229928",
    "d31f523829459cace889f16e164ebf739eebc5993580a06a54161be0fc077590",
    "de9a287da4524e7fd734db451e12a0e367b4dfb661f9654c70e0e20436016408",
    "d0efd92a7d5e1a9b520fa85c02fb5a8715c721f18b7869759589731edd4a2e9e",
    "8e88d525cb1ea326c4028835cd5b1fa22d6d0dd8640b668512ddf8d870c02c14",
    "71a4edb083dee86e5ed674b9327951a5c4f024a3eea884e64f3143aacdc48ec9",
})


def load_default(db: sqlite3.Connection, replace: bool = False) -> int:
    """Write the published corpus in the caller's transaction."""
    passage_records = read_corpus(io.StringIO(default_corpus().decode("utf-8")))
    write_corpus(db, passage_records, replace)
    db.execute("INSERT OR IGNORE INTO settings VALUES (?, '1')", (INITIALIZED,))
    return len(passage_records)


def initialize_default(db: sqlite3.Connection) -> None:
    with db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM settings WHERE name = ?", (INITIALIZED,)).fetchone():
            return
        legacy_rows = db.execute(
            "SELECT id, title, author, body FROM documents WHERE source_url = '' AND locator = ''"
        )
        retired = [(row["id"],) for row in legacy_rows
                   if sha256("\0".join(row).encode("utf-8")).hexdigest() in RETIRED_ROWS]
        if retired:
            db.executemany("DELETE FROM documents WHERE id = ?", retired)
        if retired or not db.execute("SELECT 1 FROM documents LIMIT 1").fetchone():
            load_default(db)
        else:
            db.execute("INSERT INTO settings VALUES (?, '1')", (INITIALIZED,))
