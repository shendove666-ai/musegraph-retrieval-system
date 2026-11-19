"""Application factory for the MuseGraph retrieval workbench."""

from pathlib import Path
from secrets import token_urlsafe

from flask import Flask

from . import cli, db
from .initialization import initialize_default
from .ranking import IndexCache
from .routes import bp
from .semantic import DEFAULT_MODEL, SentenceEncoder


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=str(Path(app.instance_path) / "musegraph.sqlite3"),
        AUTOLOAD_CORPUS=True,
        SECRET_KEY=None,
        SEMANTIC=False,
        SEMANTIC_MODEL=DEFAULT_MODEL,
        SEMANTIC_REVISION=None,
        MAX_CONTENT_LENGTH=512 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.config.from_prefixed_env(prefix="MUSEGRAPH")
    if test_config is not None:
        app.config.update(test_config)

    database = Path(app.config["DATABASE"])
    database.parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(db.close_db)
    with app.app_context():
        db.init_db()
        if app.config["AUTOLOAD_CORPUS"]:
            initialize_default(db.get_db())
        if not app.secret_key:
            connection = db.get_db()
            signing_key_row = connection.execute("SELECT value FROM settings WHERE name = 'secret_key'").fetchone()
            if signing_key_row is None:
                with connection:
                    connection.execute(
                        "INSERT OR IGNORE INTO settings VALUES ('secret_key', ?)", (token_urlsafe(48),)
                    )
                signing_key_row = connection.execute("SELECT value FROM settings WHERE name = 'secret_key'").fetchone()
            app.secret_key = signing_key_row[0]

    encoder = None
    if app.config["SEMANTIC"]:
        encoder = SentenceEncoder(app.config["SEMANTIC_MODEL"], app.config["SEMANTIC_REVISION"])
    app.extensions["musegraph_index"] = IndexCache(encoder)
    app.register_blueprint(bp)
    cli.register(app)
    return app
