"""Serve retrieval, evidence inspection, and session feedback."""

import sqlite3
from secrets import compare_digest, token_urlsafe

from flask import (
    Blueprint, Response, abort, current_app, redirect, render_template, request, session, url_for,
)

from . import repository
from .algorithms.fingerprint import compare as compare_texts
from .corpus import resource_path
from .db import get_db
from .ranking import MODES
from .semantic import SemanticUnavailable

bp = Blueprint("web", __name__)
QUERY_LIMIT = 1_000
COMPARISON_LIMIT = 20_000
RESULT_LIMIT = 20


def session_value(name: str) -> str:
    if name not in session:
        session[name] = token_urlsafe(24)
    return session[name]


@bp.app_context_processor
def template_globals() -> dict:
    return {"csrf_token": lambda: session_value("csrf"), "query_limit": QUERY_LIMIT}


@bp.before_request
def check_form_token() -> None:
    if request.method == "POST":
        expected = session.get("csrf", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not compare_digest(expected.encode("utf-8"), supplied.encode("utf-8")):
            abort(400, description="The form expired. Open the page again and resubmit.")


@bp.after_request
def set_headers(response):
    """Apply the response policy to routes served by the web blueprint."""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response


def modes() -> dict[str, str]:
    return {
        key: label for key, label in MODES.items()
        if key != "semantic" or current_app.config["SEMANTIC"]
    }


def search_input(values) -> tuple[str, str]:
    query = values.get("q", "").strip()
    mode = values.get("mode", "hybrid")
    if len(query) > QUERY_LIMIT or not repository.query_key(query):
        abort(400, description=f"Enter a query of 1 to {QUERY_LIMIT:,} characters containing a word or number.")
    if mode not in modes():
        abort(400, description="Choose an available retrieval mode.")
    return query, mode


@bp.get("/")
def index():
    count = get_db().execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    return render_template("index.html", modes=modes(), count=count)


@bp.get("/corpus-license")
def corpus_license():
    return Response(resource_path("GUTENBERG_LICENSE.txt").read_bytes(), mimetype="text/plain")


@bp.route("/search", methods=["GET", "POST"])
def search():
    """Record form submissions before redirecting to the ranked results view."""
    query, mode = search_input(request.form if request.method == "POST" else request.args)
    db = get_db()
    if request.method == "POST":
        repository.record_search(db, session_value("id"), query, mode)
        return redirect(url_for("web.search", q=query, mode=mode), code=303)
    votes = repository.votes_for(db, session["id"], query) if "id" in session else {}
    search_index = current_app.extensions["musegraph_index"].get(db)
    error = ""
    try:
        hits = search_index.rank(query, mode, votes)
    except SemanticUnavailable as failure:
        current_app.logger.warning("%s", failure, exc_info=True)
        error, hits = str(failure), []
    return render_template(
        "results.html", query=query, mode=mode, modes=modes(), hits=hits[:RESULT_LIMIT],
        total=len(hits), corpus_size=len(search_index.documents), error=error,
        use_semantic=current_app.config["SEMANTIC"],
    ), 503 if error else 200


@bp.get("/document/<document_id>")
def document(document_id: str):
    source_passage = repository.get_document(get_db(), document_id)
    if source_passage is None:
        abort(404)
    return render_template("document.html", document=source_passage)


@bp.post("/feedback")
def feedback():
    query, mode = search_input(request.form)
    document_id = request.form.get("document_id", "")
    choice = request.form.get("vote")
    if choice not in {"-1", "0", "1"}:
        abort(400, description="Choose relevant, off topic, or clear vote.")
    db = get_db()
    if repository.get_document(db, document_id) is None:
        abort(404)
    try:
        repository.save_vote(db, session_value("id"), query, document_id, int(choice))
    except sqlite3.IntegrityError:
        if repository.get_document(db, document_id) is None:
            abort(404)
        raise
    return redirect(url_for("web.search", q=query, mode=mode), code=303)


@bp.get("/history")
def history():
    entries = repository.get_history(get_db(), session["id"]) if "id" in session else []
    return render_template("history.html", entries=entries, modes=modes())


@bp.post("/history/clear")
def clear_history():
    if "id" in session:
        repository.clear_session(get_db(), session["id"])
    session.clear()
    return redirect(url_for("web.history"), code=303)


@bp.route("/compare", methods=["GET", "POST"])
def compare():
    left = right = error = ""
    comparison = None
    if request.method == "POST":
        left = request.form.get("left", "")
        right = request.form.get("right", "")
        if any(len(value) > COMPARISON_LIMIT or not value.strip() for value in (left, right)):
            error = f"Enter two passages of up to {COMPARISON_LIMIT:,} characters each."
        else:
            comparison = compare_texts(left, right)
    elif document_id := request.args.get("document"):
        source_passage = repository.get_document(get_db(), document_id)
        if source_passage is None:
            abort(404)
        left = source_passage.body[:COMPARISON_LIMIT]
    return render_template(
        "compare.html", left=left[:COMPARISON_LIMIT], right=right[:COMPARISON_LIMIT],
        result=comparison, error=error, limit=COMPARISON_LIMIT,
    ), 400 if error else 200
