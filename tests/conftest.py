"""Create an isolated SQLite corpus for each application test."""

import pytest

from musegraph import create_app
from musegraph.db import get_db
from musegraph.repository import Document, import_corpus


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True, "DATABASE": tmp_path / "test.sqlite3", "AUTOLOAD_CORPUS": False,
    })
    with app.app_context():
        import_corpus(get_db(), [
            Document("aria", "Recitative and aria", "Music archive",
                     "Recitative carries dialogue and advances the action in a scene."),
            Document("chorus", "The opera chorus", "Music archive",
                     "The chorus joins the action and comments on events in the opera."),
            Document("quartet", "String quartet", "Music archive",
                     "Two violins, viola, and cello share melodic material."),
        ], replace=False)
    return app


@pytest.fixture
def client(app):
    return app.test_client()
