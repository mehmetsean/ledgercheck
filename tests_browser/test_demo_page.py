"""Browser test for the demo page. Needs LEDGERCHECK_DEMO_URL and Chromium.

Run: LEDGERCHECK_DEMO_URL=http://127.0.0.1:8000/ pytest tests_browser --no-cov
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

URL = os.environ.get("LEDGERCHECK_DEMO_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set LEDGERCHECK_DEMO_URL to run")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "synthbiz-seed42-12m"
OUT = ROOT / "examples" / "ledgercheck-seed42-12m"
TABLES = ["journal_lines", "ap_invoices", "ap_payments", "vendors"]
LOAD_MS = 180_000


class Watch:
    def __init__(self) -> None:
        self.hosts: set[str] = set()
        self.errors: list[str] = []


@pytest.fixture(scope="module")
def watch() -> Watch:
    return Watch()


@pytest.fixture(scope="module")
def page(watch: Watch) -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    here = urlparse(URL).netloc
    with sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1366, "height": 900})

        def seen(request: Any) -> None:
            parts = urlparse(request.url)
            if parts.scheme in ("http", "https") and parts.netloc != here:
                watch.hosts.add(parts.netloc)

        pg.on("request", seen)
        pg.on(
            "console", lambda m: watch.errors.append(m.text) if m.type == "error" else 0
        )
        pg.on("pageerror", lambda e: watch.errors.append(str(e)))
        pg.goto(URL)
        pg.wait_for_function(
            "!document.getElementById('run-synthetic').disabled", timeout=LOAD_MS
        )
        yield pg
        browser.close()


def test_synthetic_run_renders_results(page: Any) -> None:
    page.fill("#seed", "42")
    page.fill("#months", "3")
    page.select_option("#size", "small")
    page.fill("#rate", "0.1")
    page.click("#run-synthetic")
    page.wait_for_selector("#results:not([hidden])", timeout=60_000)
    assert "Done" in page.inner_text("#status")
    assert page.locator("#rules tbody tr").count() == 9
    assert page.locator("#items tbody tr").count() > 0
    assert page.locator("#benford svg.chart").count() >= 1
    assert "status" in page.inner_text("#benford .status-line").lower()
    assert "uniform draws" in page.inner_text("#benford")
    href = page.get_attribute("#download", "href")
    assert href is not None and href.startswith("blob:")
    page.select_option("#filter-mark", "hit")
    marks = page.locator("#items tbody tr td:first-child").all_inner_texts()
    assert marks and set(marks) == {"Hit"}


def test_files_run_renders_items_and_download(page: Any) -> None:
    page.check("#mode-files")
    page.set_input_files("#file-input", [str(DATA / f"{t}.csv") for t in TABLES])
    page.wait_for_function(
        "!document.getElementById('run-files').disabled", timeout=60_000
    )
    page.click("#run-files")
    page.wait_for_function(
        "document.getElementById('status').textContent.startsWith('Done')",
        timeout=60_000,
    )
    assert page.locator("#items tbody tr").count() > 0
    assert page.locator("#rules-box").is_hidden()
    with page.expect_download() as info:
        page.click("#download")
    path = info.value.path()
    assert info.value.suggested_filename == "items_to_check.csv"
    assert Path(path).read_text("utf-8") == (OUT / "items_to_check.csv").read_text(
        "utf-8"
    )


def test_an_empty_file_gives_a_next_step(page: Any, tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", "utf-8")
    page.check("#mode-files")
    page.set_input_files("#file-input", [str(empty)])
    page.wait_for_function(
        "document.getElementById('status').textContent.includes('empty')",
        timeout=30_000,
    )
    assert "choose it again" in page.inner_text("#status")


def test_no_phone_overflow(page: Any) -> None:
    page.set_viewport_size({"width": 390, "height": 800})
    extra = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert extra <= 0
    page.set_viewport_size({"width": 1366, "height": 900})


def test_no_request_left_the_origin_and_no_errors(watch: Watch, page: Any) -> None:
    assert watch.hosts == set()
    assert watch.errors == []
