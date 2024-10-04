import random

from flask import Blueprint, redirect, render_template, request, url_for
from sqlalchemy import not_

from application.models import LocalPlan, LocalPlanDocument, Organisation, Status
from application.utils import adopted_plan_count, get_plans_query

main = Blueprint("main", __name__, template_folder="templates")


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/stats")
def stats():
    return render_template(
        "stats.html",
        plan_count=LocalPlan.query.count(),
        adopted_plan_count=adopted_plan_count(),
        plans_with_docs=get_plans_query(LocalPlan.documents.any(), count=True),
        plans_without_docs=get_plans_query(not_(LocalPlan.documents.any()), count=True),
        total_documents=LocalPlanDocument.query.count(),
        plans_with_boundary_count=get_plans_query(
            LocalPlan.local_plan_boundary.isnot(None), count=True
        ),
    )


@main.route("/randomiser")
def randomiser():
    organisations = (
        Organisation.query.filter(Organisation.end_date.is_(None))
        .order_by(Organisation.name)
        .all()
    )

    orgs_without_plan = [org for org in organisations if not org.local_plans]

    counts = {
        "orgs": len(organisations),
        "no_geography": get_plans_query(
            not_(LocalPlan.local_plan_boundary.is_(None)), count=True
        ),
        "no_documents": get_plans_query(not_(LocalPlan.documents.any()), count=True),
        "review_documents": get_plans_query(
            LocalPlan.documents.any(LocalPlanDocument.status == Status.FOR_REVIEW),
            count=True,
        ),
    }

    if "random" in request.args:
        option = request.args.get("random")

        if option == "organisation":
            random_org = random.choice(orgs_without_plan)
            return redirect(
                url_for(
                    "organisation.get_organisation", reference=random_org.organisation
                )
            )
        condition = None
        if option == "review-documents":
            condition = LocalPlan.documents.any(
                LocalPlanDocument.status == Status.FOR_REVIEW
            )
        if option == "no-documents":
            condition = not_(LocalPlan.documents.any())

        if condition is not None:
            filtered_plans = get_plans_query(condition)
            random_plan = random.choice(filtered_plans)
            return redirect(
                url_for("local_plan.get_plan", reference=random_plan.reference)
            )

    return render_template("randomiser.html", counts=counts)
