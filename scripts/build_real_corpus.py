#!/usr/bin/env python3
"""Build a passage corpus from five Project Gutenberg music-history texts."""

import argparse
import hashlib
import json
import re
import sys
import tempfile
from http.client import HTTPException
from pathlib import Path
from urllib.request import Request, urlopen

BOOKS = {
    17474: ("How to Listen to Music, 7th ed.", "Henry Edward Krehbiel"),
    28056: ("Music and Some Highly Musical People", "James Monroe Trotter"),
    70203: ("The Story of Chamber Music", "Nicholas Kilburn"),
    18444: ("The Story of the Hymns and Tunes", "Theron Brown and Hezekiah Butterworth"),
    5724: ("A Book of Operas", "Henry Edward Krehbiel"),
}
START = re.compile(r"^\*{3}\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK\b.*$", re.M | re.I)
END = re.compile(r"^\*{3}\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK\b.*$", re.M | re.I)
DOWNLOAD_LIMIT = 8 * 1024 * 1024
MIRRORS = (
    "https://mirror.cs.odu.edu/gutenberg-epub/{id}/pg{id}.txt",
    "https://gutenberg.pglaf.org/cache/epub/{id}/pg{id}.txt",
)


def extract_text(raw: bytes) -> str:
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    start = START.search(text)
    end = END.search(text, start.end()) if start else None
    if start is None or end is None:
        raise ValueError("The Gutenberg start and end markers are required.")
    return text[start.end():end.start()].strip()


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary_path = Path(stream.name)
            stream.write(raw)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def fetch(book_id: int, cache: Path, offline: bool) -> tuple[str, str]:
    cached_edition = cache / f"{book_id}.txt"
    if cached_edition.exists():
        edition_bytes = cached_edition.read_bytes()
        try:
            return extract_text(edition_bytes), hashlib.sha256(edition_bytes).hexdigest()
        except ValueError:
            if offline:
                raise
    if offline:
        raise FileNotFoundError(f"Missing cached source: {cached_edition}")
    mirror_failures = []
    for template in MIRRORS:
        url = template.format(id=book_id)
        request = Request(url, headers={"User-Agent": "MuseGraph/1.0 corpus builder"})
        try:
            with urlopen(request, timeout=45) as response:
                edition_bytes = response.read(DOWNLOAD_LIMIT + 1)
            if len(edition_bytes) > DOWNLOAD_LIMIT:
                raise ValueError("Source exceeds the download limit.")
            text = extract_text(edition_bytes)
        except (OSError, HTTPException, ValueError) as error:
            mirror_failures.append(f"{url} ({error})")
            continue
        atomic_write(cached_edition, edition_bytes)
        return text, hashlib.sha256(edition_bytes).hexdigest()
    raise OSError(f"Unable to download Gutenberg {book_id}. " + " | ".join(mirror_failures))


def build_passages(
    book_id: int, text: str, words_per_passage: int, source_sha256: str
) -> list[dict[str, str]]:
    if words_per_passage < 1:
        raise ValueError("The passage size must be positive.")
    title, author = BOOKS[book_id]
    words = list(re.finditer(r"\S+", text))
    passages = []
    for index, start in enumerate(range(0, len(words), words_per_passage), 1):
        end = min(start + words_per_passage, len(words))
        body = re.sub(r"\s+", " ", text[words[start].start():words[end - 1].end()])
        passages.append({
            "id": f"pg{book_id}-{index:04d}",
            "title": title,
            "author": author,
            "source_url": f"https://www.gutenberg.org/ebooks/{book_id}",
            "source_sha256": source_sha256,
            "passage_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "locator": f"Words {start + 1:,}–{end:,}",
            "body": body,
        })
    return passages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/generated/gutenberg.json"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    parser.add_argument("--offline", action="store_true", help="Read cached plain-text files only.")
    parser.add_argument("--book", type=int, choices=BOOKS, action="append", help="Select a book ID. Repeat to select several.")
    parser.add_argument("--words", type=int, default=180, help="Words per passage.")
    args = parser.parse_args()
    if not 40 <= args.words <= 500:
        parser.error("--words must be between 40 and 500")
    if any(args.output.resolve() == (args.cache / f"{book}.txt").resolve() for book in BOOKS):
        parser.error("--output must differ from the cached source paths")
    passage_records = []
    try:
        for book_id in sorted(set(args.book or BOOKS)):
            text, digest = fetch(book_id, args.cache, args.offline)
            passages = build_passages(book_id, text, args.words, digest)
            if not passages:
                raise ValueError(f"Gutenberg source {book_id} has no searchable text.")
            passage_records.extend(passages)
            print(f"Gutenberg {book_id}: {len(passages):,} passages, source SHA-256 {digest}")
        corpus_bytes = (json.dumps(passage_records, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        atomic_write(args.output, corpus_bytes)
    except (OSError, ValueError) as error:
        print(f"Corpus build failed: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {len(passage_records):,} passages to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
