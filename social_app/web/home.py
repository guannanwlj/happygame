"""Home blueprint (FP-001): site landing page with feature entry notes."""

from flask import Blueprint, render_template

bp = Blueprint("home", __name__)


@bp.route("/")
def index():
    """站点首页：站点名 + 引导语 + 各功能入口说明（未上线置灰）。"""
    return render_template("home/index.html")
