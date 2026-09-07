"""FP-001 tests: web application skeleton & common page frame.

Scenarios documented in docs/test-cases/fp001-web-skeleton.md. Per card §6 a
temporary demo blueprint is registered inside tests to verify that registered
routes render HTML wrapped in the base.html common layout.
"""

import sys
import types

import pytest
from flask import Blueprint, render_template_string

from social_app.app import BLUEPRINTS, create_app

SITE_NAME = "Social Platform"
HEADER_MARKER = "site-header"

DEMO_TEMPLATE = """
{% extends "base.html" %}
{% block content %}<p id="demo-content-block">demo body</p>{% endblock %}
"""


def make_demo_app():
    """create_app() plus a throwaway blueprint exercising the layout."""
    app = create_app()
    demo = Blueprint("demo", __name__)

    @demo.route("/demo")
    def demo_page():
        return render_template_string(DEMO_TEMPLATE)

    app.register_blueprint(demo)
    return app


@pytest.fixture
def client():
    return make_demo_app().test_client()


@pytest.fixture(autouse=True)
def _clean_feature_modules(monkeypatch):
    """Guarantee the three feature modules are absent (skeleton precondition).

    Also removes any stub module a test injected via sys.modules afterwards.
    """
    for module_name, _ in BLUEPRINTS:
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    yield
    for module_name, _ in BLUEPRINTS:
        sys.modules.pop(module_name, None)


class TestRegisteredRouteUsesLayout:
    """S1 / acceptance 1: registered route → 200 HTML inside base.html."""

    def test_demo_route_200_html(self, client):
        resp = client.get("/demo")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")

    def test_layout_markers_present(self, client):
        body = client.get("/demo").get_data(as_text=True)
        assert HEADER_MARKER in body
        assert SITE_NAME in body
        assert "demo-content-block" in body  # {% block content %} filled

    def test_nav_links_present(self, client):
        body = client.get("/demo").get_data(as_text=True)
        for href in ('href="/login"', 'href="/register"', 'href="/feed"', 'href="/friends"'):
            assert href in body

    def test_pending_count_defaults_to_zero(self, client):
        body = client.get("/demo").get_data(as_text=True)
        assert "pending-badge" in body
        assert ">0<" in body

    def test_pending_count_slot_is_wired(self):
        app = create_app()
        app.add_url_rule(
            "/count",
            "count",
            lambda: render_template_string(
                "{% extends 'base.html' %}"
                "{% block content %}{{ pending_count }}{% endblock %}",
                pending_count=7,
            ),
        )
        body = app.test_client().get("/count").get_data(as_text=True)
        assert "7" in body


class TestNotFoundPage:
    """S2 / acceptance 2: unknown path → rendered 404 page, no white screen."""

    def test_unknown_path_404_with_page(self, client):
        resp = client.get("/no/such/path")
        assert resp.status_code == 404
        body = resp.get_data(as_text=True)
        assert "404" in body
        assert HEADER_MARKER in body  # still framed by base.html

    def test_another_unknown_path_404(self, client):
        assert client.get("/definitely-not-here").status_code == 404


class TestRootRedirect:
    """S3 / acceptance 3: GET / → 302 to /feed."""

    def test_root_redirects_to_feed(self, client):
        resp = client.get("/")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/feed")


class TestSkeletonRobustness:
    """S4: create_app tolerates missing feature modules/blueprints."""

    def test_create_app_with_no_feature_modules(self):
        app = create_app()  # must not raise
        assert app.secret_key
        assert "/" in {r.rule for r in app.url_map.iter_rules()}

    def test_module_without_bp_attribute_is_skipped(self, monkeypatch):
        stub = types.ModuleType("social_app.auth")  # exists, no bp attribute
        monkeypatch.setitem(sys.modules, "social_app.auth", stub)
        app = create_app()
        assert "auth" not in app.blueprints

    def test_existing_blueprint_is_registered(self, monkeypatch):
        stub = types.ModuleType("social_app.auth")
        stub.bp = Blueprint("auth", "social_app.auth")
        monkeypatch.setitem(sys.modules, "social_app.auth", stub)
        app = create_app()
        assert "auth" in app.blueprints

    def test_secret_key_from_env(self, monkeypatch):
        monkeypatch.setenv("SOCIAL_SECRET_KEY", "super-secret")
        assert create_app().secret_key == "super-secret"

    def test_secret_key_default(self, monkeypatch):
        monkeypatch.delenv("SOCIAL_SECRET_KEY", raising=False)
        assert create_app().secret_key == "dev-secret"

    def test_factory_repeatable(self):
        first, second = create_app(), create_app()
        assert first is not second


class TestBlueprintsConstant:
    """Card §3.2: BLUEPRINTS lists the three feature mounts."""

    def test_blueprints_constant(self):
        assert BLUEPRINTS == [
            ("social_app.auth", "bp"),
            ("social_app.friends", "bp"),
            ("social_app.feed", "bp"),
        ]
