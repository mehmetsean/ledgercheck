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
        context = browser.new_context(viewport={"width": 1366, "height": 900})
        pg = context.new_page()

        def seen(request: Any) -> None:
            parts = urlparse(request.url)
            if parts.scheme in ("http", "https") and parts.netloc != here:
                watch.hosts.add(parts.netloc)

        def socket(ws: Any) -> None:
            watch.hosts.add("websocket " + ws.url)

        context.on("request", seen)
        pg.on("websocket", socket)
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
    assert page.evaluate("window.heldInputFiles()") == []


def test_clear_results_drops_the_download(page: Any) -> None:
    assert page.is_visible("#results")
    page.click("#clear-results")
    assert page.is_hidden("#results")
    assert page.get_attribute("#download", "href") is None
    assert page.evaluate("window.heldInputFiles()") == []


def test_run_needs_files_and_an_unset_column_says_what_to_do(page: Any) -> None:
    page.check("#mode-files")
    page.set_input_files("#file-input", [])
    assert page.is_disabled("#run-files")
    page.set_input_files("#file-input", [str(DATA / f"{t}.csv") for t in TABLES])
    page.wait_for_function(
        "!document.getElementById('run-files').disabled", timeout=60_000
    )
    page.select_option("#col-ap_invoices-amount_cents", "")
    page.click("#run-files")
    status = page.inner_text("#status")
    assert "Choose a column for amount_cents in ap_invoices" in status
    assert page.evaluate("window.heldInputFiles()") == []


def test_two_files_with_one_name_are_refused(page: Any, tmp_path: Path) -> None:
    other = tmp_path / "again"
    other.mkdir()
    (other / "vendors.csv").write_text("vendor_id,vendor_name\n", "utf-8")
    page.check("#mode-files")
    page.set_input_files(
        "#file-input", [str(DATA / "vendors.csv"), str(other / "vendors.csv")]
    )
    page.wait_for_function(
        "document.getElementById('status').textContent.includes('both named')",
        timeout=30_000,
    )
    assert page.is_disabled("#run-files")


def test_a_slash_in_a_file_name_is_refused(page: Any) -> None:
    page.check("#mode-files")
    page.set_input_files(
        "#file-input",
        [{"name": "a/b.csv", "mimeType": "text/csv", "buffer": b"x\n"}],
    )
    page.wait_for_function(
        "document.getElementById('status').textContent.includes('slash')",
        timeout=30_000,
    )


def test_the_size_cap_gives_a_next_step(page: Any, tmp_path: Path) -> None:
    big = tmp_path / "big.csv"
    big.write_text("a,b\n" + "1,2\n" * 1000, "utf-8")
    capped = page.context.new_page()
    capped.goto(URL + "?maxbytes=1000")
    capped.wait_for_function(
        "!document.getElementById('run-synthetic').disabled", timeout=LOAD_MS
    )
    capped.check("#mode-files")
    capped.set_input_files("#file-input", [str(big)])
    capped.wait_for_function(
        "document.getElementById('status').textContent.includes('more than')",
        timeout=30_000,
    )
    assert "command line" in capped.inner_text("#status")
    assert capped.is_disabled("#run-files")
    capped.close()


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
    assert page.evaluate("window.heldInputFiles()") == []


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


def test_a_raised_maxbytes_cannot_lift_the_cap(page: Any) -> None:
    raised = page.context.new_page()
    raised.goto(URL + "?maxbytes=99999999999")
    raised.wait_for_function(
        "!document.getElementById('run-synthetic').disabled", timeout=LOAD_MS
    )
    raised.check("#mode-files")
    raised.evaluate(
        """() => {
          const file = new File([new ArrayBuffer(151000000)], "huge.csv");
          const box = new DataTransfer();
          box.items.add(file);
          const input = document.getElementById("file-input");
          input.files = box.files;
          input.dispatchEvent(new Event("change"));
        }"""
    )
    raised.wait_for_function(
        "document.getElementById('status').textContent.includes('150 MB')",
        timeout=30_000,
    )
    assert raised.is_disabled("#run-files")
    raised.close()
