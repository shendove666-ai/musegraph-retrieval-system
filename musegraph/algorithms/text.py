"""Normalize words while retaining character offsets for evidence display."""

import re
import unicodedata
from dataclasses import dataclass


_ASCII_WORD = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)*")


@dataclass(frozen=True, slots=True)
class Token:
    term: str
    start: int
    end: int


def _normalize_term(word: str) -> str:
    return unicodedata.normalize("NFKC", word).casefold().replace("’", "'")


def scan(text: str) -> list[Token]:
    """Return normalized words and their original half-open character spans."""
    if text.isascii():
        return [
            Token(_normalize_term(match.group()), match.start(), match.end())
            for match in _ASCII_WORD.finditer(text)
        ]

    tokens = []
    cursor = 0
    while cursor < len(text):
        if not text[cursor].isalnum():
            cursor += 1
            continue
        start = cursor
        cursor += 1
        while cursor < len(text):
            char = text[cursor]
            internal_apostrophe = (
                char in "'’" and cursor + 1 < len(text) and text[cursor + 1].isalnum()
            )
            if not (char.isalnum() or internal_apostrophe or unicodedata.category(char).startswith("M")):
                break
            cursor += 1
        term = _normalize_term(text[start:cursor])
        tokens.append(Token(term, start, cursor))
    return tokens


def terms(text: str) -> list[str]:
    return [token.term for token in scan(text)]
