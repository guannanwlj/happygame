"""FP-002 Web 服务与应用骨架单元测试（任务卡 §7 验收 / §8 验证方式）。"""

import pytest
from flask import Blueprint, flash, render_template_string

import social_app
from social_app import create_app

# 路由规划表全部固定路径（顶栏导航必须逐条输出；含 <int:req_id> 的两条
# 由 FP-007 待处理列表页按请求 id 寻址，不作字面 href，见设计说明决策 4）。
NAV_HREFS = [
    "/",
    "/register",
    "/login",
    "/logout",
    "/friends/requests",
    "/friends",
    "/posts/new",
    "/feed",
]

CHILD_TEMPLATE = (
    '{% extends "base.html" %}'
    "{% block title %}示例子页{% endblock %}"
    '{% block content %}<p id="child-content">子页内容</p>{% endblock %}'
)


@pytest.fixture()
def app():
    app = create_app()
    app.testing = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


# --- S1 首页渲染 -----------------------------------------------------------


def test_home_page_renders_layout_and_welcome(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    body = response.get_data(as_text=True)
    assert "<!DOCTYPE html>" in body
    assert "<nav" in body
    assert "欢迎" in body
    assert "导航" in body


@pytest.mark.parametrize("href", NAV_HREFS)
def test_navigation_contains_every_planned_fixed_path(client, href):
    body = client.get("/").get_data(as_text=True)
    assert f'href="{href}"' in body


# --- S2 蓝图挂载点 ---------------------------------------------------------


def test_dummy_blueprint_mount_point_works(app):
    bp = Blueprint("dummy", __name__)

    @bp.get("/__dummy__")
    def dummy():
        return "dummy-ok"

    app.register_blueprint(bp)

    response = app.test_client().get("/__dummy__")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "dummy-ok"


def test_create_app_invokes_blueprint_registry(monkeypatch):
    calls = []

    def fake_register_blueprints(app):
        calls.append(app)

    monkeypatch.setattr(social_app, "register_blueprints", fake_register_blueprints)
    app = create_app()
    assert calls == [app]


# --- S3 模板继承 -----------------------------------------------------------


def test_child_template_fills_title_and_content_blocks(app):
    with app.test_request_context():
        body = render_template_string(CHILD_TEMPLATE)
    assert "<title>示例子页" in body
    assert 'id="child-content"' in body
    assert "<nav" in body


def test_flash_message_area_renders_flashed_messages(app):
    with app.test_request_context():
        flash("你好，骨架")
        body = render_template_string(CHILD_TEMPLATE)
    assert "你好，骨架" in body


# --- S4 会话密钥 -----------------------------------------------------------


def test_secret_key_reads_environment_override(monkeypatch):
    monkeypatch.setenv("SOCIAL_SECRET_KEY", "test-secret-from-env")
    assert create_app().secret_key == "test-secret-from-env"


def test_secret_key_falls_back_to_dev_constant(monkeypatch):
    monkeypatch.delenv("SOCIAL_SECRET_KEY", raising=False)
    assert create_app().secret_key == "dev-secret"


# --- S5 边界 ---------------------------------------------------------------


def test_create_app_returns_fresh_instance_each_call():
    assert create_app() is not create_app()
