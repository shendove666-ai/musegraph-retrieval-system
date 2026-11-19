"""Exercise the browser routes, form validation, and session isolation."""

import re

from musegraph.db import get_db
from musegraph.repository import Document, import_corpus
from musegraph.semantic import SemanticUnavailable


def token(client, page="/"):
    response = client.get(page)
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()


def test_search_and_document(client):
    response = client.post("/search", data={
        "q": "recitative carries dialogue and advances the action in a scene",
        "mode": "hybrid", "csrf_token": token(client),
    }, follow_redirects=True)
    assert response.status_code == 200
    assert response.history[0].status_code == 303
    assert b"Shared phrase" in response.data
    assert b"/document/aria" in response.data
    assert b"Matched terms" in response.data
    assert b"Recitative and aria" in client.get("/document/aria").data
    assert client.get("/document/missing").status_code == 404
    assert response.headers["Cache-Control"] == "no-store"


def test_feedback_is_scoped_and_reversible(app, client):
    csrf = token(client)
    other = app.test_client()
    vote = {"q": "action", "mode": "lexical", "document_id": "chorus", "csrf_token": csrf}
    for choice, adjustment in [("1", b"+0.15"), ("-1", b"-0.15"), ("0", b"0.00")]:
        response = client.post("/feedback", data={**vote, "vote": choice}, follow_redirects=True)
        assert response.status_code == 200
        assert adjustment in response.data
        if choice != "0":
            assert adjustment in client.get("/search?q=ACTION!&mode=hybrid").data
            assert adjustment not in other.get("/search?q=action&mode=lexical").data
            assert adjustment not in client.get("/search?q=opera&mode=lexical").data
        else:
            assert b"Clear vote" not in response.data


def test_history_deduplicates_and_clears_feedback(client):
    csrf = token(client)
    for query in ("Action", "action!"):
        assert client.post("/search", data={"q": query, "csrf_token": csrf}).status_code == 303
    client.post("/feedback", data={
        "q": "action", "document_id": "chorus", "vote": "1", "csrf_token": csrf,
    })
    history = client.get("/history")
    assert history.data.count(b"<time ") == 1
    assert b"action!" in history.data
    client.get("/search?q=recitative")
    assert client.get("/history").data.count(b"<time ") == 1
    response = client.post("/history/clear", data={"csrf_token": csrf}, follow_redirects=True)
    assert b"No searches recorded" in response.data
    assert b"+0.15" not in client.get("/search?q=action").data


def test_compare_has_verified_offsets_and_escapes_markup(client):
    csrf = token(client, "/compare")
    response = client.post("/compare", data={
        "csrf_token": csrf, "left": "<em>One two three four five six seven eight.</em>",
        "right": "ONE, two three four five six seven eight!",
    })
    assert response.status_code == 200
    assert b"Shared phrases" in response.data
    assert b"Characters " in response.data
    assert b"&lt;em&gt;" in response.data
    assert b"Recitative carries dialogue" in client.get("/compare?document=aria").data


def test_form_rejections_and_empty_results(client):
    assert client.post("/search", data={"q": "opera"}).status_code == 400
    assert client.get("/search?q=+++").status_code == 400
    assert client.get("/search?q=music&mode=semantic").status_code == 400
    assert client.get("/search", query_string={"q": "x" * 1001}).status_code == 400
    assert b"No matching passages" in client.get("/search?q=unfindableword").data
    csrf = token(client)
    assert client.post("/compare", data={
        "csrf_token": csrf, "left": "a" * 20_001, "right": "hello",
    }).status_code == 400
    assert client.post("/feedback", data={
        "csrf_token": csrf, "q": "opera", "document_id": "aria", "vote": "8",
    }).status_code == 400


def test_corpus_revision_invalidates_process_index(app, client):
    assert b"No matching passages" in client.get("/search?q=clarinet").data
    with app.app_context():
        import_corpus(get_db(), [Document("clarinet", "Clarinet", "Archive", "Single reed.")], False)
    assert b"/document/clarinet" in client.get("/search?q=clarinet").data


def test_semantic_failure_offers_lexical_route(app, client, monkeypatch):
    class UnavailableEncoder:
        def passages(self, _text):
            raise SemanticUnavailable("The semantic model could not be loaded.")

    app.config["SEMANTIC"] = True
    monkeypatch.setattr(app.extensions["musegraph_index"], "encoder", UnavailableEncoder())
    response = client.get("/search?q=action&mode=semantic")
    assert response.status_code == 503
    assert b"Search with TF-IDF" in response.data
    assert client.get("/search?q=action&mode=lexical").status_code == 200


def test_warm_search_reads_do_not_scale_with_match_count(app, client):
    with client.session_transaction() as browser_session:
        browser_session["id"] = "test-session"

    assert client.get("/search?q=recitative&mode=lexical").status_code == 200
    with app.app_context():
        statements = []
        db = get_db()
        db.set_trace_callback(statements.append)
        try:
            for query, matches in [("recitative", 1), ("action", 2)]:
                statements.clear()
                response = client.get("/search", query_string={"q": query, "mode": "lexical"})
                assert response.status_code == 200
                assert response.data.count(b'class="panel result"') == matches
                reads = [statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]
                assert len(reads) == 2
                assert "FROM feedback" in reads[0]
                assert "FROM corpus_revision" in reads[1]
        finally:
            db.set_trace_callback(None)
