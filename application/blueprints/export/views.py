from flask import Blueprint, jsonify

from application.export import LocalPlanEventModel, LocalPlanModel
from application.models import LocalPlan, LocalPlanEvent, Status

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


@export.route("/local-plan-events", methods=["GET"])
def export_local_plan_events():
    data = []
    for event in LocalPlanEvent.query.filter(
        LocalPlanEvent.event_data.is_(None),
        LocalPlanEvent.end_date.is_(None),
        LocalPlanEvent.event_date.isnot(None),
    ).all():
        model = LocalPlanEventModel.model_validate(event)
        data.append(model.model_dump(by_alias=True))
    return jsonify(data)


@export.route("/boundaries", methods=["GET"])
def export_boundaries():
    pass


@export.route("/documents", methods=["GET"])
def export_documents():
    pass
