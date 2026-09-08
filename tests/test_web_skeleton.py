"""Tests for the FP-001 web skeleton (task card §7/§8)."""

import flask
import pytest

from social_app.web import FEATURES, create_app

SITE_NAME = "社交小站"


def _client(app):
    return app.test_client()


# A. Acceptance 1 — factory + home page


def test_create_app_returns_flask_instance():
    app = create_app()
    assert isinstance(app, flask.Flask)


def test_home_page_renders_with_site_name_and_guide():
    resp = _client(create_app()).get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert SITE_NAME in body
    assert "引导" in body or "欢迎" in body


def test_base_layout_provides_flash_region_and_nav():
    body = _client(create_app()).get("/").get_data(as_text=True)
    assert 'class="flashes"' in body  # flash message region from base.html
    assert "<nav" in body  # nav area from base.html


def test_future_feature_entries_are_grayed_not_linked():
    body = _client(create_app()).get("/").get_data(as_text=True)
    assert 'class="entry disabled"' in body
    for href in ('href="/login"', 'href="/register"', 'href="/posts"'):
        assert href not in body


# B. Acceptance 2 — blueprint mount rule


def test_probe_blueprint_mountable_on_factory_product():
    probe_bp = flask.Blueprint("probe", __name__)

    @probe_bp.route("/__probe__")
    def probe():
        return "probe-ok"

    app = create_app(features=())
    app.register_blueprint(probe_bp)
    resp = _client(app).get("/__probe__")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "probe-ok"


def test_explicit_features_home_registered():
    app = create_app(features=("home",))
    assert _client(app).get("/").status_code == 200


def test_default_features_is_home_tuple():
    assert FEATURES == ("home",)


def test_unknown_feature_name_raises_clear_import_error():
    with pytest.raises(ImportError) as excinfo:
        create_app(features=("home", "no_such_module"))
    message = str(excinfo.value)
    assert "no_such_module" in message
    assert "social_app.web.no_such_module" in message


def test_feature_module_without_bp_raises_clear_import_error(tmp_path, monkeypatch):
    # B4: a module named social_app/web/<name>.py that exists but has no `bp`.
    bad_dir = tmp_path / "social_app" / "web"
    bad_dir.mkdir(parents=True)
    (bad_dir / "__init__.py").write_text("", encoding="utf-8")
    (bad_dir / "bpless.py").write_text("X = 1\n", encoding="utf-8")
    for pkg in ("social_app", "social_app.web"):
        module = __import__(pkg, fromlist=["_"])
        monkeypatch.setattr(module, "__path__", [str(tmp_path.joinpath(*pkg.split(".")))])
    with pytest.raises(ImportError) as excinfo:
        create_app(features=("bpless",))
    assert "bpless" in str(excinfo.value)


# C. Acceptance 4 — SECRET_KEY configuration


def test_secret_key_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv("SOCIAL_SECRET_KEY", raising=False)
    assert create_app().config["SECRET_KEY"] == "dev-secret-key"


def test_secret_key_taken_from_env(monkeypatch):
    monkeypatch.setenv("SOCIAL_SECRET_KEY", "some-test-key")
    assert create_app().config["SECRET_KEY"] == "some-test-key"


# D. Error pages


def test_404_page_is_friendly():
    resp = _client(create_app()).get("/nope")
    assert resp.status_code == 404
    body = resp.get_data(as_text=True)
    assert "404" in body
    assert "页面不存在" in body
    assert 'class="flashes"' in body  # error page still extends base layout


def test_500_page_is_friendly():
    boom = flask.Blueprint("boom", __name__)

    @boom.route("/__boom__")
    def boom_view():
        raise RuntimeError("boom")

    app = create_app(features=())
    app.register_blueprint(boom)
    resp = _client(app).get("/__boom__")
    assert resp.status_code == 500
    body = resp.get_data(as_text=True)
    assert "500" in body
    assert "出错了" in body or "稍后再试" in body
