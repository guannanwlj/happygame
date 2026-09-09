"""FP-004 tests: preference dimension configuration (itinerary_app/prefs.py).

Scenarios documented in docs/test-cases/fp004-prefs.md. Temp configs are
written under tmp_path (card §6: temp JSON with an added 「同行人」dimension
or adjusted labels proves the config is data-driven).
"""

import json

import pytest

from itinerary_app.prefs import (
    DEFAULT_CONFIG_PATH,
    PreferenceConfigError,
    load_preferences,
)

EXPECTED_DEFAULT_KEYS = ["budget", "pace", "interest", "diet", "transport"]
EXPECTED_FREE_TEXT = {
    "key": "notes",
    "label": "补充说明",
    "placeholder": "其他偏好或约束（选填）",
}


def write_config(tmp_path, config, name="preferences.json", raw=None):
    """Write a config file (object, or literal `raw` text) and return its path."""
    path = tmp_path / name
    path.write_text(
        raw if raw is not None else json.dumps(config, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(path)


def default_config():
    """A parsed copy of the shipped default config, safe to mutate."""
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


class TestDefaultLoad:
    """Acceptance 1: the shipped file loads into the full structure."""

    def test_five_dimensions_with_key_label_options(self):
        config = load_preferences()
        dimensions = config["dimensions"]
        assert [dim["key"] for dim in dimensions] == EXPECTED_DEFAULT_KEYS
        for dim in dimensions:
            assert isinstance(dim["key"], str) and dim["key"]
            assert isinstance(dim["label"], str) and dim["label"]
            assert isinstance(dim["options"], list) and dim["options"]
            assert all(
                isinstance(option, str) and option for option in dim["options"]
            )

    def test_known_initial_labels_and_options(self):
        config = load_preferences()
        by_key = {dim["key"]: dim for dim in config["dimensions"]}
        assert by_key["budget"]["label"] == "预算档位"
        assert by_key["budget"]["options"] == ["经济", "舒适", "高档"]
        assert by_key["transport"]["options"] == [
            "公共交通优先",
            "打车优先",
            "租车自驾",
            "徒步友好",
        ]

    def test_free_text_item(self):
        assert load_preferences()["free_text"] == EXPECTED_FREE_TEXT

    def test_default_path_equals_explicit_package_path(self):
        assert load_preferences(None) == load_preferences(str(DEFAULT_CONFIG_PATH))


class TestConfigDriven:
    """Acceptance 2: editing the file (not the code) changes what loads."""

    def test_added_dimension_returns(self, tmp_path):
        config = default_config()
        config["dimensions"].append(
            {"key": "companions", "label": "同行人", "options": ["成人", "儿童", "宠物同行"]}
        )
        path = write_config(tmp_path, config)

        loaded = load_preferences(path)
        assert [dim["key"] for dim in loaded["dimensions"]] == (
            EXPECTED_DEFAULT_KEYS + ["companions"]
        )
        companions = loaded["dimensions"][-1]
        assert companions["label"] == "同行人"
        assert companions["options"] == ["成人", "儿童", "宠物同行"]
        assert loaded["free_text"] == EXPECTED_FREE_TEXT

    def test_adjusted_labels_and_options_return(self, tmp_path):
        config = default_config()
        budget = config["dimensions"][0]
        budget["label"] = "预算档位（新）"
        budget["options"] = ["穷游", "标准", "轻奢", "奢华"]

        loaded = load_preferences(write_config(tmp_path, config))
        assert loaded["dimensions"][0]["label"] == "预算档位（新）"
        assert loaded["dimensions"][0]["options"] == ["穷游", "标准", "轻奢", "奢华"]
        assert "经济" not in loaded["dimensions"][0]["options"]

    def test_removed_dimension_does_not_return(self, tmp_path):
        config = default_config()
        config["dimensions"] = [
            dim for dim in config["dimensions"] if dim["key"] != "diet"
        ]

        loaded = load_preferences(write_config(tmp_path, config))
        assert [dim["key"] for dim in loaded["dimensions"]] == [
            key for key in EXPECTED_DEFAULT_KEYS if key != "diet"
        ]

    def test_extra_unknown_fields_pass_through(self, tmp_path):
        config = default_config()
        config["dimensions"][0]["hint"] = "验证期试验字段"
        config["schema_version"] = 2

        loaded = load_preferences(write_config(tmp_path, config))
        assert loaded["dimensions"][0]["hint"] == "验证期试验字段"
        assert loaded["schema_version"] == 2


class TestInvalidConfig:
    """Acceptance 3 + edge paths: malformed configs raise with a reason."""

    def test_missing_dimensions_key(self, tmp_path):
        config = default_config()
        del config["dimensions"]
        with pytest.raises(PreferenceConfigError, match="dimensions"):
            load_preferences(write_config(tmp_path, config))

    def test_dimensions_wrong_type(self, tmp_path):
        for bad in ("budget", {"budget": []}, 5):
            config = default_config()
            config["dimensions"] = bad
            with pytest.raises(PreferenceConfigError, match="dimensions"):
                load_preferences(write_config(tmp_path, config))

    def test_dimensions_empty_list(self, tmp_path):
        config = default_config()
        config["dimensions"] = []
        with pytest.raises(PreferenceConfigError, match="dimensions"):
            load_preferences(write_config(tmp_path, config))

    @pytest.mark.parametrize("field", ["key", "label", "options"])
    def test_dimension_missing_field(self, tmp_path, field):
        config = default_config()
        del config["dimensions"][2][field]
        with pytest.raises(PreferenceConfigError, match=field):
            load_preferences(write_config(tmp_path, config))

    @pytest.mark.parametrize("field", ["key", "label"])
    def test_dimension_text_field_bad_type_or_empty(self, tmp_path, field):
        for bad in (7, None, "", "   "):
            config = default_config()
            config["dimensions"][1][field] = bad
            with pytest.raises(PreferenceConfigError, match=field):
                load_preferences(write_config(tmp_path, config))

    def test_dimension_not_an_object(self, tmp_path):
        config = default_config()
        config["dimensions"][0] = ["budget", "预算档位"]
        with pytest.raises(PreferenceConfigError, match="dimensions\\[0\\]"):
            load_preferences(write_config(tmp_path, config))

    @pytest.mark.parametrize("bad", ["经济", 3, []])
    def test_options_wrong_type_or_empty(self, tmp_path, bad):
        config = default_config()
        config["dimensions"][0]["options"] = bad
        with pytest.raises(PreferenceConfigError, match="options"):
            load_preferences(write_config(tmp_path, config))

    @pytest.mark.parametrize("bad", [10, "", None])
    def test_option_item_not_non_empty_string(self, tmp_path, bad):
        config = default_config()
        config["dimensions"][0]["options"] = ["经济", bad, "高档"]
        with pytest.raises(PreferenceConfigError, match="options\\[1\\]"):
            load_preferences(write_config(tmp_path, config))

    def test_duplicate_dimension_keys(self, tmp_path):
        config = default_config()
        config["dimensions"].append(dict(config["dimensions"][0]))
        with pytest.raises(PreferenceConfigError, match="budget"):
            load_preferences(write_config(tmp_path, config))

    def test_missing_free_text(self, tmp_path):
        config = default_config()
        del config["free_text"]
        with pytest.raises(PreferenceConfigError, match="free_text"):
            load_preferences(write_config(tmp_path, config))

    @pytest.mark.parametrize(
        ("mutate", "reason"),
        [
            (lambda ft: ft.pop("key"), "key"),
            (lambda ft: ft.pop("placeholder"), "placeholder"),
            (lambda ft: ft.update(label=11), "label"),
        ],
    )
    def test_free_text_malformed(self, tmp_path, mutate, reason):
        config = default_config()
        mutate(config["free_text"])
        with pytest.raises(PreferenceConfigError, match=reason):
            load_preferences(write_config(tmp_path, config))

    def test_free_text_not_an_object(self, tmp_path):
        config = default_config()
        config["free_text"] = "notes"
        with pytest.raises(PreferenceConfigError, match="free_text"):
            load_preferences(write_config(tmp_path, config))

    def test_top_level_not_an_object(self, tmp_path):
        path = write_config(tmp_path, None, raw=json.dumps([1, 2, 3]))
        with pytest.raises(PreferenceConfigError, match="对象"):
            load_preferences(path)

    def test_invalid_json_text(self, tmp_path):
        path = write_config(tmp_path, None, raw="{'dimensions': }")
        with pytest.raises(PreferenceConfigError, match="JSON"):
            load_preferences(path)

    def test_nonexistent_path(self, tmp_path):
        path = tmp_path / "no-such-file.json"
        with pytest.raises(PreferenceConfigError) as excinfo:
            load_preferences(str(path))
        assert "no-such-file.json" in str(excinfo.value)

    def test_error_is_value_error(self):
        assert issubclass(PreferenceConfigError, ValueError)
