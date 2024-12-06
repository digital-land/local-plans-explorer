from flask import Blueprint, jsonify

from application.export import LocalPlanModel, LocalPlanTimetableModel
from application.models import LocalPlan, LocalPlanTimetable, Status

export = Blueprint("export", __name__, url_prefix="/export")


@export.route("/local-plans", methods=["GET"])
def export_local_plans():
    local_plans = LocalPlan.query.filter(
        LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED])
    ).all()
    data = []
    for plan in local_plans:
        model = LocalPlanModel.model_validate(plan)
        data.append(model.model_dump(by_alias=True))
    return jsonify(data)


@export.route("/local-plan-timetables", methods=["GET"])
def export_local_plan_timetables():
    data = []
    timetables = (
        LocalPlanTimetable.query.join(LocalPlanTimetable.local_plan)
        .filter(
            LocalPlanTimetable.event_data.is_(None),
            LocalPlanTimetable.end_date.is_(None),
            LocalPlanTimetable.event_date.isnot(None),
            LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED]),
        )
        .all()
    )
    for timetable in timetables:
        model = LocalPlanTimetableModel.model_validate(timetable)
        data.append(model.model_dump(by_alias=True))
    return jsonify(data)


@export.route("/boundaries", methods=["GET"])
def export_boundaries():
    pass


@export.route("/documents", methods=["GET"])
def export_documents():
    pass
