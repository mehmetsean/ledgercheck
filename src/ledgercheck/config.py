"""Load the column map and the settings from small JSON files."""

import json
from dataclasses import fields
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .io import SPECS, plain
from .models import ColumnMap, DuplicateSettings, Settings

MAX_JSON_BYTES = 1_000_000
MAX_SETTING = 10**15
MAX_DAYS = 3_660
MAX_CLOSE_DAYS = 31
MAX_HOLIDAYS = 10_000
MAX_SKIP_USERS = 10_000
MAX_USER_ID = 200
ARTICLES: dict[Any, str] = {int: "an integer", float: "a number", bool: "true or false"}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > MAX_JSON_BYTES:
            raise ValueError(f"{plain(path.name)}: file is too large")
        data = json.loads(path.read_text("utf-8-sig"))
    except OSError as e:
        raise ValueError(
            f"{plain(path.name)}: could not read the file ({e.strerror})"
        ) from None
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ValueError(f"{plain(path.name)}: not valid JSON") from None
    if not isinstance(data, dict):
        raise ValueError(f"{plain(path.name)}: top level must be an object")
    return data


def _check_keys(name: str, where: str, data: dict[str, Any], allowed: set[str]) -> None:
    for key in data:
        if key not in allowed:
            raise ValueError(f"{name}: unknown key {ascii(key)[:40]} in {where}")


def _string_map(name: str, where: str, data: Any, allowed: set[str]) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ValueError(f"{name}: {where} must be an object")
    _check_keys(name, where, data, allowed)
    for value in data.values():
        if not isinstance(value, str) or not value:
            raise ValueError(f"{name}: every value in {where} must be non-empty text")
    return dict(data)


def load_column_map(path: Path) -> ColumnMap:
    data = _load_json(path)
    name = plain(path.name)
    _check_keys(
        name, "the top level", data, {"files", "columns", "date_format", "amounts"}
    )
    tables = set(SPECS)
    files = _string_map(name, "files", data.get("files", {}), tables)
    columns: dict[str, dict[str, str]] = {}
    raw = data.get("columns", {})
    if not isinstance(raw, dict):
        raise ValueError(f"{name}: columns must be an object")
    _check_keys(name, "columns", raw, tables)
    for table, mapping in raw.items():
        allowed = {f for f, _ in SPECS[table]}
        columns[table] = _string_map(name, f"columns.{table}", mapping, allowed)
    amounts = data.get("amounts", "cents")
    if amounts not in ("cents", "dollars"):
        raise ValueError(f"{name}: amounts must be cents or dollars")
    fmt = data.get("date_format", "%Y-%m-%d")
    _check_date_format(name, fmt)
    return ColumnMap(files=files, columns=columns, date_format=fmt, amounts=amounts)


def _check_date_format(name: str, fmt: Any) -> None:
    ok = isinstance(fmt, str) and 0 < len(fmt) <= 20
    if ok:
        try:
            sample = date(2001, 2, 3)
            ok = datetime.strptime(sample.strftime(fmt), fmt).date() == sample
        except ValueError:
            ok = False
    if not ok:
        raise ValueError(f"{name}: date_format is not a usable date format")


def _number(name: str, key: str, value: Any, kind: type) -> Any:
    if kind is float and isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    if kind is int and isinstance(value, int) and not isinstance(value, bool):
        return value
    if kind is bool and isinstance(value, bool):
        return value
    raise ValueError(f"{name}: {key} must be {ARTICLES[kind]}")


def _fill(name: str, data: dict[str, Any], cls: type, skip: set[str]) -> dict[str, Any]:
    kinds: dict[str, Any] = {f.name: f.type for f in fields(cls)}
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key in skip:
            continue
        if key not in kinds:
            raise ValueError(f"{name}: unknown setting {ascii(key)[:40]}")
        out[key] = _number(name, key, value, kinds[key])
    return out


def _user_list(name: str, raw: Any) -> tuple[str, ...]:
    ok = isinstance(raw, list) and len(raw) <= MAX_SKIP_USERS
    if ok:
        ok = all(
            isinstance(x, str) and 0 < len(x) <= MAX_USER_ID and x == x.strip()
            for x in raw
        )
    if not ok:
        raise ValueError(f"{name}: rare_skip_users must be a list of user ids")
    return tuple(raw)


def load_settings(path: Path, data_limit: int | None = None) -> Settings:
    data = _load_json(path)
    name = plain(path.name)
    own = {"extra_holidays", "duplicates", "rare_skip_users"}
    values = _fill(name, data, Settings, own)
    if data_limit is not None and "approval_limit_cents" not in values:
        values["approval_limit_cents"] = data_limit
    holidays: list[date] = []
    raw = data.get("extra_holidays", [])
    if not isinstance(raw, list):
        raise ValueError(f"{name}: extra_holidays must be a list of dates")
    if len(raw) > MAX_HOLIDAYS:
        raise ValueError(f"{name}: extra_holidays has more than {MAX_HOLIDAYS} dates")
    for item in raw:
        try:
            holidays.append(date.fromisoformat(item))
        except (TypeError, ValueError):
            raise ValueError(f"{name}: extra_holidays needs YYYY-MM-DD dates") from None
    skip = _user_list(name, data.get("rare_skip_users", []))
    dup = data.get("duplicates", {})
    if not isinstance(dup, dict):
        raise ValueError(f"{name}: duplicates must be an object")
    dup_values = _fill(name, dup, DuplicateSettings, set())
    settings = Settings(
        extra_holidays=tuple(holidays),
        duplicates=DuplicateSettings(**dup_values),
        rare_skip_users=skip,
        **values,
    )
    _check_ranges(name, settings)
    return settings


def _check_ranges(name: str, s: Settings) -> None:
    d = s.duplicates
    whole = {
        "approval_limit_cents": s.approval_limit_cents,
        "round_step_cents": s.round_step_cents,
        "rare_min_entries": s.rare_min_entries,
        "split_window_days": s.split_window_days,
        "window_days": d.window_days,
        "max_cell_steps": d.max_cell_steps,
        "recurring_min_count": d.recurring_min_count,
    }
    for key, value in whole.items():
        if abs(value) > MAX_SETTING:
            raise ValueError(f"{name}: {key} must be at most {MAX_SETTING}")
    checks = [
        (s.approval_limit_cents > 0, "approval_limit_cents must be above 0"),
        (s.round_step_cents > 0, "round_step_cents must be above 0"),
        (0 <= s.rare_share <= 1, "rare_share must be from 0 to 1"),
        (s.rare_min_entries >= 1, "rare_min_entries must be at least 1"),
        (
            0 <= s.split_window_days <= MAX_DAYS,
            f"split_window_days must be 0 to {MAX_DAYS}",
        ),
        (
            0 <= s.close_window_days <= MAX_CLOSE_DAYS,
            f"close_window_days must be 0 to {MAX_CLOSE_DAYS}",
        ),
        (0 < s.split_band <= 1, "split_band must be above 0 and at most 1"),
        (0 <= d.window_days <= MAX_DAYS, f"window_days must be 0 to {MAX_DAYS}"),
        (0 <= d.name_threshold <= 1, "name_threshold must be from 0 to 1"),
        (0 <= d.invoice_threshold <= 1, "invoice_threshold must be from 0 to 1"),
        (d.max_cell_steps >= 1, "max_cell_steps must be at least 1"),
        (
            d.recurring_min_count == 0 or d.recurring_min_count >= 2,
            "recurring_min_count must be 0 or at least 2",
        ),
    ]
    for ok, message in checks:
        if not ok:
            raise ValueError(f"{name}: {message}")
