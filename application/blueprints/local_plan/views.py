from flask import Blueprint, abort, render_template

from application.models import LocalPlan

local_plan = Blueprint("local_plan", __name__, url_prefix="/local-plan")


@local_plan.route("/")
def index():
    return render_template("local_plan/index.html")


@local_plan.route("/<string:reference>")
def get_local_plan(reference):
    lp = LocalPlan.query.get(reference)
    if lp is None:
        return abort(404)
    return render_template("local_plan/local-plan.html", local_plan=lp)
