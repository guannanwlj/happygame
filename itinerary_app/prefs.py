"""Preference dimension configuration for the itinerary planner (FP-004).

The package data file `preferences.json` is the single source of truth for
the preference dimensions (multi-choice preset label groups) and the free
text supplement item. `load_preferences()` is the S5 provider contract:
FP-005 (form rendering) and FP-007 (prompt building) consume it. Iterating
the dimension set means editing the JSON file (restart applies it), never
the code.
"""

import json
from pathlib import Path
from typing import NoReturn

DEFAULT_CONFIG_PATH = Path(__file__).with_name("preferences.json")


class PreferenceConfigError(ValueError):
    """The preference config file is missing or structurally invalid."""


def _fail(reason: str, path: Path) -> NoReturn:
    raise PreferenceConfigError(f"偏好配置错误（{path}）：{reason}")


def _require_text(value: object, where: str, path: Path) -> None:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{where} 必须为非空字符串，实际为 {value!r}", path)


def _validate_dimensions(dimensions: object, path: Path) -> None:
    if not isinstance(dimensions, list) or not dimensions:
        _fail("dimensions 必须为非空的维度列表", path)
    seen_keys: set[str] = set()
    for index, dimension in enumerate(dimensions):
        where = f"dimensions[{index}]"
        if not isinstance(dimension, dict):
            _fail(f"{where} 必须为 JSON 对象，实际为 {dimension!r}", path)
        for field in ("key", "label", "options"):
            if field not in dimension:
                _fail(f"{where} 缺少 {field} 字段", path)
        _require_text(dimension["key"], f"{where}.key", path)
        _require_text(dimension["label"], f"{where}.label", path)
        options = dimension["options"]
        if not isinstance(options, list) or not options:
            _fail(f"{where}.options 必须为非空字符串列表，实际为 {options!r}", path)
        for option_index, option in enumerate(options):
            _require_text(option, f"{where}.options[{option_index}]", path)
        if dimension["key"] in seen_keys:
            _fail(f"维度 key 重复：{dimension['key']!r}", path)
        seen_keys.add(dimension["key"])


def _validate_free_text(free_text: object, path: Path) -> None:
    if not isinstance(free_text, dict):
        _fail(f"free_text 必须为 JSON 对象，实际为 {free_text!r}", path)
    for field in ("key", "label", "placeholder"):
        if field not in free_text:
            _fail(f"free_text 缺少 {field} 字段", path)
        _require_text(free_text[field], f"free_text.{field}", path)


def _validate(config: object, path: Path) -> dict:
    if not isinstance(config, dict):
        _fail(f"顶层必须为 JSON 对象，实际为 {config!r}", path)
    if "dimensions" not in config:
        _fail("缺少 dimensions 字段", path)
    _validate_dimensions(config["dimensions"], path)
    if "free_text" not in config:
        _fail("缺少 free_text 字段", path)
    _validate_free_text(config["free_text"], path)
    return config


def load_preferences(config_path: str | None = None) -> dict:
    """Load and validate the preference config (S5 provider contract).

    `config_path=None` reads the package-internal `preferences.json`;
    an explicit path is read as-is. Raises `PreferenceConfigError` with
    the reason (missing file, invalid JSON, missing `dimensions`, wrong
    field types, ...) — never returns a half-validated structure.
    """
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PreferenceConfigError(f"偏好配置文件不存在：{path}") from exc
    except OSError as exc:
        raise PreferenceConfigError(f"偏好配置文件不可读取：{path}（{exc}）") from exc
    except json.JSONDecodeError as exc:
        raise PreferenceConfigError(f"偏好配置不是合法 JSON：{path}（{exc}）") from exc
    return _validate(raw, path)
