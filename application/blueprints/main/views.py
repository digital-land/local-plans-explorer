from flask import Blueprint, render_template
from sqlalchemy import not_

from application.models import LocalPlan, LocalPlanDocument
from application.utils import adopted_plan_count, get_plans_query, plan_count

main = Blueprint("main", __name__, template_folder="templates")


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/stats")
def stats():
    return render_template(
        "stats.html",
        plan_count=plan_count(),
        adopted_plan_count=adopted_plan_count(),
        local_plan_count=plan_count(),
        plans_with_docs=get_plans_query(LocalPlan.documents.any(), count=True),
        plans_without_docs=get_plans_query(not_(LocalPlan.documents.any()), count=True),
        total_documents=LocalPlanDocument.query.count(),
        plans_with_boundary_count=get_plans_query(
            LocalPlan.local_plan_boundary.isnot(None), count=True
        ),
    )


# @main.route("/randomiser")
# def randomiser():
#     adopted_local_plans = get_adopted_local_plans()
#     organisations = get_organisations_expected_to_publish_plan()
#     orgs_with_adopted_lp = [
#         organisation
#         for plan in adopted_local_plans
#         for organisation in plan.organisations
#     ]
#     orgs_without_adopted_lp = _exclude_orgs(organisations, orgs_with_adopted_lp)

#     counts = {
#         "orgs": len(orgs_without_adopted_lp),
#         "no_geography": get_plans_query(
#             not_(DevelopmentPlan.development_plan_boundary.is_(None)), count=True
#         ),
#         "no_documents": get_plans_query(
#             not_(DevelopmentPlan.documents.any()), count=True
#         ),
#         "no_events": get_plans_query(not_(DevelopmentPlan.timetable.any()), count=True),
#     }

#     if "random" in request.args:
#         option = request.args.get("random")

#         # for org with no adopted local plan
#         if option == "organisation":
#             random_org = random.choice(orgs_without_adopted_lp)
#             return redirect(
#                 url_for("organisation.organisation", reference=random_org.organisation)
#             )

#         # for plans missing something
#         condition = None
#         if option == "missing-geography":
#             condition = not_(DevelopmentPlan.geography.has())
#         if option == "no-documents":
#             condition = not_(DevelopmentPlan.documents.any())
#         if option == "no-events":
#             condition = not_(DevelopmentPlan.timetable.any())

#         if condition is not None:
#             filtered_plans = get_plans_query(condition)
#             random_plan = random.choice(filtered_plans)
#             return redirect(
#                 url_for("development_plan.plan", reference=random_plan.reference)
#             )

#     return render_template("randomiser.html", counts=counts)


def _exclude(main_list, to_exclude, attr_name="reference"):
    items_to_remove = [getattr(item, attr_name) for item in to_exclude]
    return [
        item for item in main_list if getattr(item, attr_name) not in items_to_remove
    ]
