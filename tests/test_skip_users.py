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
    assert (before, after) == (78, 31)
    rows = (tmp_path / "b" / "items_to_check.csv").read_text("utf-8")
    assert "SYSTEM_" not in "\n".join(
        x for x in rows.splitlines() if "rare_poster" in x
    )


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


def test_measure_script_shows_na_when_nothing_is_flagged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert measure_skip_users.show(None) == "n/a"
    assert measure_skip_users.show(0.5) == "0.5000"
    assert measure_skip_users.main(["--seeds", "42", "--shares", "0"]) == 0
    assert "| 0.0 | none | 0 | n/a | 0.0000 |" in capsys.readouterr().out


@pytest.mark.parametrize(
    "seeds", ["1-2-3", "a-b", "-5", "5-1", "1-201", "x", "1,,2", ""]
)
def test_bad_seeds_are_a_usage_error(seeds: str) -> None:
    with pytest.raises(SystemExit) as e:
        measure_skip_users.main(["--seeds", seeds])
    assert e.value.code == 2


@pytest.mark.parametrize("shares", ["2", "-0.1", "x", "0.1,1.5", ""])
def test_bad_shares_are_a_usage_error(shares: str) -> None:
    with pytest.raises(SystemExit) as e:
        measure_skip_users.main(["--shares", shares])
    assert e.value.code == 2


def test_seed_cap() -> None:
    assert len(measure_skip_users.seed_list("1-200")) == 200
