import json
import shutil
import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from synthbiz.generate import Params, generate
from synthbiz.io import write_dataset

from ledgercheck import evaluate as ev
from ledgercheck.cli import main
from ledgercheck.config import MAX_SETTING, load_settings


def manifest(folder: Path, body: object) -> None:
    (folder / "manifest.json").write_text(json.dumps(body))


def test_no_manifest_gives_none(tmp_path: Path) -> None:
    assert ev.read_manifest_limit(tmp_path) is None


def test_manifest_without_the_key_gives_none(tmp_path: Path) -> None:
    manifest(tmp_path, {"parameters": {}})
    assert ev.read_manifest_limit(tmp_path) is None


def test_manifest_limit_is_read(tmp_path: Path) -> None:
    manifest(tmp_path, {"approval_limit_cents": 250_000})
    assert ev.read_manifest_limit(tmp_path) == 250_000


@pytest.mark.parametrize("bad", ["5", True, 0, -1, 1.5, None, MAX_SETTING + 1])
def test_bad_manifest_limit_is_an_error(tmp_path: Path, bad: object) -> None:
    manifest(tmp_path, {"approval_limit_cents": bad})
    with pytest.raises(ValueError, match="approval_limit_cents"):
        ev.read_manifest_limit(tmp_path)


def test_manifest_not_json_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("[1")
    with pytest.raises(ValueError, match="manifest"):
        ev.read_manifest_limit(tmp_path)


def test_manifest_not_an_object_is_an_error(tmp_path: Path) -> None:
    manifest(tmp_path, [1])
    with pytest.raises(ValueError, match="manifest"):
        ev.read_manifest_limit(tmp_path)


def test_manifest_symlink_is_refused(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text("{}")
    (tmp_path / "manifest.json").symlink_to(real)
    with pytest.raises(ValueError, match="symbolic link"):
        ev.read_manifest_limit(tmp_path)


def test_settings_file_value_beats_manifest(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text('{"approval_limit_cents": 100}')
    assert load_settings(path, 999).approval_limit_cents == 100


def test_manifest_value_fills_a_missing_key(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text('{"rare_share": 0.1}')
    s = load_settings(path, 999)
    assert s.approval_limit_cents == 999
    assert s.rare_share == 0.1


@given(st.integers(min_value=1, max_value=MAX_SETTING))
def test_any_valid_manifest_limit_round_trips(limit: int) -> None:
    with tempfile.TemporaryDirectory() as name:
        folder = Path(name)
        manifest(folder, {"approval_limit_cents": limit})
        assert ev.read_manifest_limit(folder) == limit


def test_default_stays_without_a_manifest(tmp_path: Path) -> None:
    assert ev.read_manifest_limit(tmp_path) is None


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("lim")
    write_dataset(generate(Params(seed=42, size="small", months=12)), folder)
    return folder


def split_count(out: Path) -> int:
    return (out / "items_to_check.csv").read_text("utf-8").count("split_under_limit")


def test_run_uses_the_data_limit(synthetic: Path, tmp_path: Path) -> None:
    same = tmp_path / "same"
    shutil.copytree(synthetic, same)
    assert main(["run", str(same), "--out", str(tmp_path / "a")]) == 0
    other = tmp_path / "other"
    shutil.copytree(synthetic, other)
    body = json.loads((other / "manifest.json").read_text("utf-8"))
    body["approval_limit_cents"] = 1_000_000
    manifest(other, body)
    assert main(["run", str(other), "--out", str(tmp_path / "b")]) == 0
    assert split_count(tmp_path / "a") != split_count(tmp_path / "b")


def test_run_matches_today_with_the_synthbiz_limit(
    synthetic: Path, tmp_path: Path
) -> None:
    bare = tmp_path / "bare"
    shutil.copytree(synthetic, bare)
    (bare / "manifest.json").unlink()
    assert main(["run", str(synthetic), "--out", str(tmp_path / "a")]) == 0
    assert main(["run", str(bare), "--out", str(tmp_path / "b")]) == 0
    a = (tmp_path / "a" / "items_to_check.csv").read_text("utf-8")
    b = (tmp_path / "b" / "items_to_check.csv").read_text("utf-8")
    assert a == b
