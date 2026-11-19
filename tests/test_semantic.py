"""Exercise the real embedding model when explicitly enabled."""

import os
import io

import pytest

from musegraph import create_app
from musegraph.corpus import default_corpus
from musegraph.db import get_db
from musegraph.repository import import_corpus, read_corpus
from musegraph.semantic import DEFAULT_MODEL


@pytest.mark.skipif(
    os.getenv("MUSEGRAPH_TEST_SEMANTIC") != "1",
    reason="Set MUSEGRAPH_TEST_SEMANTIC=1 to run the real SentenceTransformer test.",
)
def test_semantic_search_through_flask(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": tmp_path / "semantic.sqlite3",
        "AUTOLOAD_CORPUS": False,
        "SEMANTIC": True,
        "SEMANTIC_MODEL": os.getenv("MUSEGRAPH_TEST_MODEL", DEFAULT_MODEL),
    })
    documents = read_corpus(io.StringIO(default_corpus().decode("utf-8")))
    selected = {"pg18444-0040", "pg70203-0040"}
    with app.app_context():
        import_corpus(get_db(), [doc for doc in documents if doc.id in selected], replace=False)
    client = app.test_client()
    query = "the tune called Leoni and the synagogue singer Meyer Lyon"
    response = client.get("/search", query_string={"q": query, "mode": "semantic"})
    assert response.status_code == 200
    assert b"Sentence-BERT" in response.data
    assert b"Meyer Lyon" in response.data
    assert b"/document/pg18444-0040" in response.data
