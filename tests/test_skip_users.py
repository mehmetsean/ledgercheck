import json
import sys
from pathlib import Path

import pytest
from synthbiz.generate import Params, generate
from synthbiz.io import write_dataset

from ledgercheck.cli import main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_skip_users  # noqa: E402


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("skip")
    write_dataset(
        generate(Params(seed=42, size="large", months=12, anomaly_rate=0.1)), folder
    )
    return folder


def rare_count(data: Path, out: Path, settings: dict[str, object]) -> int:
    path = out.parent / (out.name + ".json")
    path.write_text(json.dumps(settings))
    args = ["run", str(data), "--out", str(out), "--settings", str(path)]
    assert main(args) == 0
    return (out / "items_to_check.csv").read_text("utf-8").count("rare_poster")


def test_settings_file_skips_system_users(synthetic: Path, tmp_path: Path) -> None:
    wide = {"rare_share": 0.1}
    both = {"rare_share": 0.1, "rare_skip_users": ["SYSTEM_BATCH", "SYSTEM_RECURRING"]}
    before = rare_count(synthetic, tmp_path / "a", wide)
    after = rare_count(synthetic, tmp_path / "b", both)
    assert after < before


def test_default_is_unchanged(synthetic: Path, tmp_path: Path) -> None:
    plain = rare_count(synthetic, tmp_path / "a", {})
    empty = rare_count(synthetic, tmp_path / "b", {"rare_skip_users": []})
    assert plain == empty


def test_measure_script_prints_a_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert measure_skip_users.main(["--seeds", "42", "--shares", "0.1"]) == 0
    out = capsys.readouterr().out
    assert "| 0.1 | none | 78 |" in out
    assert "| 0.1 | system users | 31 |" in out


def test_seed_list() -> None:
    assert measure_skip_users.seed_list("3-5") == [3, 4, 5]
    assert measure_skip_users.seed_list("1,9") == [1, 9]
