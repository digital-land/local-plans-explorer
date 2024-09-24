from flask import Blueprint, abort, render_template

from application.models import LocalPlan, LocalPlanDocument

document = Blueprint(
    "document",
    __name__,
    url_prefix="/local-plan/<string:local_plan_reference>/document",
)


@document.route("/")
def index(local_plan_reference):
    lp = LocalPlan.query.get(local_plan_reference)
    if lp is None:
        return abort(404)
    return render_template("document/index.html", local_plan=lp)


@document.route("/<string:reference>")
def get_local_plan(local_plan_reference, reference):
    lp_doc = LocalPlanDocument.query.get(reference)
    if lp_doc is None:
        return abort(404)
    return render_template("document/document.html", local_plan_document=lp_doc)
