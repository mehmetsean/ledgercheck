import ast
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest
from synthbiz.generate import Params, generate
from synthbiz.io import write_dataset

from helpers import ledger, line
from ledgercheck import cli
from ledgercheck import evaluate as ev
from ledgercheck.eval_report import folder_text, markdown, metrics_dict, metrics_text
from ledgercheck.io import read_folder
from ledgercheck.measured import FUZZY_LIMIT, load_measured
from ledgercheck.report import DISCLAIMER, NOTICE

SAT = date(2025, 3, 8)
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "ledgercheck"
GOLDEN = Path(__file__).parent / "golden" / "metrics_small.json"
SMALL_GRID = ev.Grid((0.6, 0.8), (0.6, 0.8), (0.05, 0.1))
PARAMS = ev.EvalParams("small", 3, 0.3)
COMMAND = "ledgercheck evaluate --size small --months 3 --rate 0.3"


def small_report() -> ev.EvalReport:
    return ev.evaluate_seeds(
        [1, 2], [101, 102, 103], PARAMS, ev.DEFAULT_COSTS, SMALL_GRID
    )


def test_adapter_matches_writing_files_and_reading_them(tmp_path: Path):
    ds = generate(Params(seed=7, months=3, size="small", anomaly_rate=0.3))
    write_dataset(ds, tmp_path / "d")
    assert ev.ledger_from_dataset(ds.tables) == read_folder(tmp_path / "d")
    assert ev.labels_from_dataset(ds.labels) == ev.read_labels(tmp_path / "d")


def test_synthbiz_journal_labels_point_to_the_first_line_of_the_entry():
    ds = generate(Params(seed=7, months=3, size="small", anomaly_rate=0.3))
    first = {}
    for row in ds.tables["journal_lines"]:
        first.setdefault(row["je_id"], []).append(row["line_id"])
    labels = [x for x in ds.labels if x["table"] == "journal_lines"]
    assert labels
    for x in labels:
        entry = next(
            r["je_id"]
            for r in ds.tables["journal_lines"]
            if r["line_id"] == x["row_id"]
        )
        assert x["row_id"] == min(first[entry])


def test_folder_mode_matches_the_in_memory_score(tmp_path: Path):
    ds = generate(Params(seed=7, months=3, size="small", anomaly_rate=0.3))
    write_dataset(ds, tmp_path / "d")
    settings = ev.settings_for(0.8, 0.8, 0.05)
    scores, count = ev.evaluate_folder(tmp_path / "d", settings, ev.DEFAULT_COSTS)
    ledger = ev.ledger_from_dataset(ds.tables)
    flags = ev.all_flags(ledger, settings)
    direct = ev.score(
        flags, ev.labels_from_dataset(ds.labels), ledger, ev.DEFAULT_COSTS
    )
    assert scores == direct
    assert count == len(ds.labels)


def test_evaluation_is_repeatable():
    assert metrics_text(metrics_dict(small_report(), COMMAND)) == metrics_text(
        metrics_dict(small_report(), COMMAND)
    )


def test_golden_metrics():
    text = metrics_text(metrics_dict(small_report(), COMMAND))
    assert text == GOLDEN.read_text("utf-8")


def test_tuning_uses_only_tuning_seeds():
    other = ev.evaluate_seeds(
        [5, 6], [101, 102, 103], PARAMS, ev.DEFAULT_COSTS, SMALL_GRID
    )
    assert other.report_seeds == small_report().report_seeds
    assert small_report().tune_seeds == (1, 2)


def test_months_above_the_synthbiz_limit_is_an_error():
    too_long = ev.EvalParams("small", ev.max_months() + 1, 0.1)
    with pytest.raises(ValueError, match="months must be at most"):
        ev.evaluate_seeds([1], [2], too_long, ev.DEFAULT_COSTS, SMALL_GRID)


def test_missing_synthbiz_names_the_eval_extra(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(__import__("sys").modules, "synthbiz.check", None)
    with pytest.raises(ValueError, match="eval extra"):
        ev.max_months()


def test_default_rate_matches_synthbiz():
    assert ev.DEFAULT_RATE == Params().anomaly_rate


def test_default_grid_runs_from_0_6_to_0_95():
    assert ev.THRESHOLDS[0] == 0.6 and ev.THRESHOLDS[-1] == 0.95
    assert len(ev.THRESHOLDS) == 8


def run_cli(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    code = cli.main(args)
    got = capsys.readouterr()
    return code, got.out, got.err


def test_cli_folder_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    ds = generate(Params(seed=7, months=3, size="small", anomaly_rate=0.3))
    write_dataset(ds, tmp_path / "d")
    code, out, _ = run_cli(["evaluate", str(tmp_path / "d")], capsys)
    assert code == 0
    assert (
        "weekend_posting" in out and "placeholders" in out and "Decision support" in out
    )
    assert "planted rate 0.3" in out
    assert NOTICE in out and DISCLAIMER in out


def test_cli_seed_mode_writes_the_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    out_dir = tmp_path / "out"
    args = ["evaluate", "--size", "small", "--months", "2", "--tune-seeds", "1-2"]
    args += ["--seeds", "10-12", "--rate", "0.2", "--out", str(out_dir)]
    code, out, _ = run_cli(args, capsys)
    assert code == 0 and "Settings chosen" in out
    assert NOTICE in out and DISCLAIMER in out
    names = sorted(p.name for p in out_dir.iterdir())
    assert names == ["README.txt", "evaluation.html", "evaluation.md", "metrics.json"]
    md = (out_dir / "evaluation.md").read_text("utf-8")
    for text in (
        "measured on synthetic data (synthbiz)",
        "Report seeds 10-12",
        "placeholders",
        FUZZY_LIMIT,
        "percentile bootstrap",
    ):
        assert text in md
    page = (out_dir / "evaluation.html").read_text("utf-8")
    assert "<script" not in page and "http" not in page.replace(
        "https://www.linkedin", ""
    )
    doc = json.loads((out_dir / "metrics.json").read_text("utf-8"))
    assert doc["planted"]["anomaly_rate"] == 0.2
    again, _, err = run_cli(args, capsys)
    assert again == 2 and "not empty" in err
    forced, _, _ = run_cli(args + ["--force"], capsys)
    assert forced == 0


def test_cli_custom_costs_are_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    costs = tmp_path / "c.json"
    costs.write_text('{"check_cost": 7}')
    args = ["evaluate", "--months", "2", "--tune-seeds", "1", "--seeds", "2-3"]
    args += ["--costs", str(costs), "--out", str(tmp_path / "o")]
    assert run_cli(args, capsys)[0] == 0
    md = (tmp_path / "o" / "evaluation.md").read_text("utf-8")
    assert "Costs used: check cost 7.0" in md
    assert f"--costs {costs}" in md
    doc = json.loads((tmp_path / "o" / "metrics.json").read_text("utf-8"))
    assert doc["costs"]["check_cost"] == 7.0
    assert doc["command"].endswith(f"--costs {costs}")


@pytest.mark.parametrize(
    "args, message",
    [
        (["--out", "X", "--seeds", "5-1"], "backwards"),
        (["--out", "X", "--seeds", "1-201"], "at most 200"),
        (["--out", "X", "--tune-seeds", "1-51"], "at most 50"),
        (["--out", "X", "--months", "200"], "seeds times months"),
        (["--out", "X", "--tune-seeds", "abc"], "--tune-seeds"),
        (["--out", "X", "--tune-seeds", "1-5", "--seeds", "5-9"], "share a seed"),
        (["--out", "X", "--months", "0"], "--months"),
        (["--out", "X", "--months", "999999"], "--months"),
        (["--out", "X", "--months", "x"], "--months"),
        (["--out", "X", "--size", "huge"], "--size"),
        (["--out", "X", "--rate", "2"], "--rate"),
        (["--out", "X", "--rate", "nan"], "--rate"),
        (["--out", "X", "--rate", "abc"], "--rate"),
        ([], "--out"),
        (["--out", "X", "--settings", "s.json"], "--settings"),
        (["--out", "X", "--costs", "missing.json"], "missing.json"),
    ],
)
def test_cli_bad_options_give_one_line_and_exit_2(
    args: list[str], message: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    fixed = [str(tmp_path / "x") if a == "X" else a for a in args]
    code, out, err = run_cli(["evaluate", *fixed], capsys)
    assert code == 2 and out == ""
    assert message in err and len(err.strip().splitlines()) == 1


def test_cli_folder_with_seed_options_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code, _, err = run_cli(["evaluate", str(tmp_path), "--seeds", "1-2"], capsys)
    assert code == 2 and "cannot be combined" in err


def test_cli_folder_without_labels_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    ds = generate(Params(seed=7, months=2, size="small"))
    write_dataset(ds, tmp_path / "d")
    (tmp_path / "d" / "labels.csv").unlink()
    code, _, err = run_cli(["evaluate", str(tmp_path / "d")], capsys)
    assert code == 2 and "labels.csv" in err


def test_cli_without_synthbiz_says_to_install_the_eval_extra(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setitem(__import__("sys").modules, "synthbiz.check", None)
    code, _, err = run_cli(["evaluate", "--out", str(tmp_path / "o")], capsys)
    assert code == 2 and "eval extra" in err


def test_cli_refuses_a_folder_with_other_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    (tmp_path / "keep.txt").write_text("x")
    code, _, err = run_cli(["evaluate", "--out", str(tmp_path), "--force"], capsys)
    assert code == 2 and "not ledgercheck output" in err


def test_run_output_shows_the_shipped_measured_rates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    ds = generate(Params(seed=7, months=2, size="small"))
    write_dataset(ds, tmp_path / "d")
    assert (
        run_cli(["run", str(tmp_path / "d"), "--out", str(tmp_path / "o")], capsys)[0]
        == 0
    )
    md = (tmp_path / "o" / "analysis.md").read_text("utf-8")
    html = (tmp_path / "o" / "analysis.html").read_text("utf-8")
    doc = load_measured()
    assert doc is not None
    for text in (md, html):
        assert "Measured on synthetic data" in text
        assert "Report seeds 101-130" in text
        assert "duplicate_fuzzy" in text
    assert "the measured rates are shown" in md
    assert "Run defaults" in md and "do not predict" in md
    assert "A 1.0000 to 1.0000 interval means every report seed" in md


def load_script():
    spec = importlib.util.spec_from_file_location(
        "make_measured", ROOT / "scripts/make_measured.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_make_measured_writes_then_checks_then_detects_a_change(tmp_path: Path):
    script = load_script()
    path = tmp_path / "m.json"
    small = ["--size", "small", "--months", "2", "--tune-seeds", "1", "--seeds", "2-3"]
    small += ["--path", str(path)]
    assert script.main(small) == 0
    assert script.main(small + ["--check"]) == 0
    path.write_text(path.read_text("utf-8").replace("2000", "1999"), "utf-8")
    assert script.main(small + ["--check"]) == 1


def test_make_measured_passes_on_a_bad_option(tmp_path: Path):
    script = load_script()
    with pytest.raises(SystemExit):
        script.build(
            type(
                "A",
                (),
                {
                    "size": "small",
                    "months": "0",
                    "tune_seeds": "1",
                    "seeds": "2",
                    "rate": "0.1",
                },
            )()
        )


def test_folder_text_cleans_and_caps_label_details(tmp_path: Path):
    lines = [line("JE-1", SAT, line_id="L1")]
    details = "x" * 200 + "\x1b[31m"
    lab = [ev.Label("journal_lines", "L1", "weekend_posting", details)]
    scores = ev.score([], lab, ledger(lines=lines), ev.DEFAULT_COSTS)
    info = {"seed": "1", "size": "\x1b[2Jbig", "months": "3", "anomaly_rate": "0.1"}
    text = folder_text(scores, 1, info, ev.DEFAULT_COSTS)
    assert "\x1b" not in text
    shown = [x for x in text.splitlines() if x.startswith("missed by")]
    assert len(shown) == 1 and len(shown[0]) == len("missed by weekend_posting: ") + 80


def test_evaluation_shows_defaults_and_tuned_rows():
    doc = metrics_dict(small_report(), COMMAND)
    md = markdown(doc)
    assert "rare_poster (defaults)" in md
    assert "rare_poster (tuned on seeds 1-2)" in md
    assert "duplicate_fuzzy (tuned on seeds 1-2)" in md
    assert "split_under_limit (tuned" not in md
    assert doc["settings"]["defaults"]["rare_share"] == 0.05


def test_shipped_measured_json_is_complete():
    doc = load_measured()
    assert doc is not None
    assert doc["synthetic"] is True and doc["command"].startswith(
        "ledgercheck evaluate"
    )
    assert set(doc["rules"]) == set(ev.SCORED_RULES)
    assert doc["costs"]["placeholder"] is True


def imports_of(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


@pytest.mark.parametrize("name", ["rules", "duplicates", "benford"])
def test_core_rules_never_import_evaluate(name: str):
    names = imports_of(SRC / f"{name}.py")
    assert not {n for n in names if "evaluate" in n or "eval_report" in n}
    assert "importlib" not in names
    tree = ast.parse((SRC / f"{name}.py").read_text("utf-8"))
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "__import__" not in called


def strings_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text("utf-8"))
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def test_only_evaluate_names_labels_and_manifest_files():
    for path in SRC.glob("*.py"):
        named = [t for t in strings_of(path) if t in ("labels.csv", "manifest.json")]
        assert bool(named) == (path.name == "evaluate.py"), path.name
