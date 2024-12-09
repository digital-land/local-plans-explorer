import csv
import io

from flask import Blueprint, Response

from application.export import (
    LocalPlanBoundaryModel,
    LocalPlanDocumentModel,
    LocalPlanModel,
    LocalPlanTimetableModel,
)
from application.models import LocalPlan, LocalPlanDocument, LocalPlanTimetable, Status

export = Blueprint("export", __name__, url_prefix="/export")


@export.get("/local-plan.csv")
def export_local_plans():
    local_plans = LocalPlan.query.filter(
        LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED])
    ).all()
    data = []
    for plan in local_plans:
        model = LocalPlanModel.model_validate(plan)
        data.append(model.model_dump(by_alias=True))
    output = _to_csv(data, LocalPlanModel)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=local-plan.csv"},
    )


@export.get("/local-plan-timetable.csv")
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
    output = _to_csv(data, LocalPlanModel)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=local-plan-timetable.csv"},
    )


@export.get("/local-plan-boundary.csv")
def export_boundaries():
    local_plans = LocalPlan.query.filter(
        LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED]),
        LocalPlan.boundary_status.in_([Status.FOR_PLATFORM, Status.EXPORTED]),
    ).all()
    data = []
    for plan in local_plans:
        model = LocalPlanBoundaryModel.model_validate(plan.boundary)
        data.append(model.model_dump(by_alias=True))
    output = _to_csv(data, LocalPlanBoundaryModel)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=local-plan-boundary.csv"},
    )


@export.get("/local-plan-document.csv")
def export_documents():
    data = []
    documents = LocalPlanDocument.query.filter(
        LocalPlanDocument.status.in_([Status.FOR_PLATFORM, Status.EXPORTED])
    ).all()
    for document in documents:
        model = LocalPlanDocumentModel.model_validate(document)
        data.append(model.model_dump(by_alias=True))
    output = _to_csv(data, LocalPlanDocumentModel)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=local-plan-document.csv"},
    )


def _to_csv(data, model):
    if not data:
        # Return empty CSV with headers if no data
        fieldnames = [
            field.alias for field in model.model_fields.values() if field.alias
        ]
    else:
        fieldnames = data[0].keys()
    output = io.StringIO()
    fieldnames = data[0].keys()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in data:
        writer.writerow(row)
    return output.getvalue()
