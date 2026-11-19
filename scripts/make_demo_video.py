#!/usr/bin/env python3
"""Record a browser walkthrough of the bundled Gutenberg collection."""

import argparse
import logging
import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from werkzeug.serving import make_server

from musegraph import create_app

ROOT = Path(__file__).resolve().parents[1]
QUERY = "Only the music as Leoni sang it prompted his own song"
PASSAGE_ID = "pg18444-0041"
VIEWPORT = {"width": 1440, "height": 1080}


@contextmanager
def serve(directory: Path):
    """Start a loopback server with an independent database and a warm index."""
    app = create_app({
        "DATABASE": str(directory / "demo.sqlite3"),
        "SECRET_KEY": None,
        "AUTOLOAD_CORPUS": True,
        "SEMANTIC": True,
        "SESSION_COOKIE_SECURE": False,
    })
    print("Preparing the Gutenberg corpus and semantic index.", flush=True)
    with app.test_client() as client:
        response = client.get("/search", query_string={"q": QUERY, "mode": "hybrid"})
        if response.status_code != 200 or b"Sentence-BERT" not in response.data:
            raise RuntimeError(
                "The hybrid index could not start. Check the semantic dependency and model weights."
            )
    server = make_server("127.0.0.1", 0, app, threaded=True)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


def capture(page, directory: Path, number: int, seconds: int) -> None:
    page.screenshot(path=directory / f"frame_{number}.png", animations="disabled")
    page.wait_for_timeout(seconds * 1000)


def walkthrough(page, url: str, directory: Path, expect) -> None:
    response = page.goto(url)
    if response is None or not response.ok:
        raise RuntimeError("The browser could not open the MuseGraph home page.")
    expect(page.get_by_text("2286 indexed passages", exact=True)).to_be_visible()
    capture(page, directory, 0, 3)

    page.get_by_label("Topic or quotation").fill(QUERY)
    page.get_by_label("Retrieval mode").select_option("hybrid")
    page.get_by_role("button", name="Search", exact=True).click()
    top_result_card = page.locator("ol.results > li").first
    title = top_result_card.get_by_role("link", name="The Story of the Hymns and Tunes")
    expect(title).to_have_attribute("href", f"/document/{PASSAGE_ID}")
    expect(top_result_card.get_by_text("Sentence-BERT", exact=True)).to_be_visible()
    expect(top_result_card.get_by_text("Shared phrase", exact=False)).to_be_visible()
    capture(page, directory, 1, 5)

    top_result_card.get_by_role("button", name="Relevant", exact=True).click()
    expect(page.get_by_text("+0.15", exact=True)).to_be_visible()
    page.wait_for_timeout(2500)
    title.click()
    page.get_by_text("Source verification", exact=True).click()
    expect(page.get_by_text("Passage SHA-256", exact=True)).to_be_visible()
    page.evaluate("window.scrollTo(0, 0)")
    capture(page, directory, 2, 5)

    page.get_by_role("link", name="Compare this passage").click()
    page.get_by_label("Second passage").fill(QUERY)
    page.get_by_role("button", name="Compare", exact=True).click()
    expect(page.get_by_role("heading", name="Shared phrases")).to_be_visible()
    expect(page.locator(".matches mark").first).to_be_visible()
    capture(page, directory, 3, 5)

    page.get_by_role("link", name="History", exact=True).click()
    expect(page.get_by_role("link", name=QUERY, exact=True)).to_be_visible()
    capture(page, directory, 4, 4)


def record(directory: Path, channel: str | None, executable: str) -> None:
    from playwright.sync_api import expect, sync_playwright

    with serve(directory) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel)
        try:
            context = browser.new_context(
                viewport=VIEWPORT, device_scale_factor=1,
                record_video_dir=directory, record_video_size=VIEWPORT,
            )
            try:
                page = context.new_page()
                page.set_default_timeout(20_000)
                video = page.video
                walkthrough(page, url, directory, expect)
            finally:
                context.close()
        finally:
            browser.close()
        if video is None:
            raise RuntimeError("The browser did not produce a video recording.")
        source = video.path()

    subprocess.run(
        [
            executable, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(directory / "musegraph_demo.mp4"),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "demo")
    parser.add_argument("--browser-channel", choices=("chrome", "msedge"))
    args = parser.parse_args()

    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        args.output.mkdir(parents=True, exist_ok=True)
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        with TemporaryDirectory(prefix="musegraph-demo-", dir=args.output) as scratch:
            directory = Path(scratch)
            record(directory, args.browser_channel, get_ffmpeg_exe())
            names = [f"frame_{number}.png" for number in range(5)]
            names.append("musegraph_demo.mp4")
            for name in names:
                (directory / name).replace(args.output / name)
    except ImportError as error:
        parser.exit(1, f"Install the demo extra and retry: {error}\n")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Demo recording failed: {error}\n")

    print(f"Saved five screenshots and the video to {args.output.resolve()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
