"""Expose the MuseGraph application through Flask's command group."""

from flask.cli import FlaskGroup

from . import create_app
from .benchmark import evaluate_command


def main() -> None:
    FlaskGroup(name="musegraph", create_app=create_app, commands={"evaluate": evaluate_command})()


if __name__ == "__main__":
    main()
