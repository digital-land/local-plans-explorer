from flask import Blueprint, abort, render_template, request
from sqlalchemy.orm import joinedload, load_only, noload

from application.models import LocalPlan, Organisation, Status

organisation = Blueprint("organisation", __name__, url_prefix="/organisation")


@organisation.route("/")
def organisations():
    plan_status_filter = request.args.get("planStatusFilter", None)
    if plan_status_filter and plan_status_filter != "all":
        status = Status[plan_status_filter]
        orgs = (
            Organisation.query.options(
                load_only(
                    Organisation.name, Organisation.end_date, Organisation.organisation
                ),
                joinedload(Organisation.local_plans),
                noload(Organisation.local_plan_boundaries),
                noload(Organisation.local_plan_documents),
            )
            .filter(Organisation.end_date.is_(None))
            .filter(Organisation.local_plans.any(LocalPlan.status == status))
            .order_by(Organisation.name)
            .all()
        )
    else:
        orgs = (
            Organisation.query.options(
                load_only(
                    Organisation.name, Organisation.end_date, Organisation.organisation
                ),
                joinedload(Organisation.local_plans),
                noload(Organisation.local_plan_boundaries),
                noload(Organisation.local_plan_documents),
            )
            .filter(Organisation.end_date.is_(None))
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
    has_archived = any(
        plan.status == Status.NOT_FOR_PLATFORM for plan in org.local_plans
    )
    if org is None:
        return abort(404)
    return render_template(
        "organisation/organisation.html", organisation=org, has_archived=has_archived
    )
