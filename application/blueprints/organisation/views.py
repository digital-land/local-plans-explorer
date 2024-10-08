from flask import Blueprint, abort, redirect, render_template, request, url_for

from application.models import LocalPlan, Organisation, Status

organisation = Blueprint("organisation", __name__, url_prefix="/organisation")


@organisation.route("/")
def organisations():
    if "organisation" in request.args:
        lpa = request.args.get("organisation")
        return redirect(
            url_for("organisation.organisation", reference=f"local-authority-eng:{lpa}")
        )

    plan_status_filter = request.args.get("planStatusFilter", None)
    if plan_status_filter and plan_status_filter != "all":
        status = Status[plan_status_filter]
        orgs = (
            Organisation.query.filter(Organisation.end_date.is_(None))
            .filter(Organisation.local_plans.any(LocalPlan.status == status))
            .order_by(Organisation.name)
            .all()
        )
    else:
        orgs = (
            Organisation.query.filter(Organisation.end_date.is_(None))
            .order_by(Organisation.name)
            .all()
        )

    return render_template(
        "organisation/index.html",
        organisations=orgs,
        statuses=Status,
        plan_status_filter=request.args.get("planStatusFilter"),
    )


@organisation.route("/<string:reference>")
def get_organisation(reference):
    org = Organisation.query.get(reference)
    if org is None:
        return abort(404)
    return render_template("organisation/organisation.html", organisation=org)
