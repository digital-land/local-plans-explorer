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

    ended_timetables = (
        LocalPlanTimetable.query.join(LocalPlanTimetable.local_plan)
        .filter(
            LocalPlanTimetable.event_data.isnot(None),
            LocalPlanTimetable.end_date.isnot(None),
            LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED]),
        )
        .all()
    )

    for timetable in ended_timetables:
        data.extend(_to_legacy_timetable(timetable))

    current_timetables = (
        LocalPlanTimetable.query.join(LocalPlanTimetable.local_plan)
        .filter(
            LocalPlanTimetable.event_data.is_(None),
            LocalPlanTimetable.end_date.is_(None),
            LocalPlanTimetable.event_date.isnot(None),
            LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED]),
        )
        .all()
    )
    for timetable in current_timetables:
        model = LocalPlanTimetableModel.model_validate(timetable)
        if model.organisation is None or model.organisation.strip() == "":
            if not timetable.local_plan.is_joint_plan():
                model.organisation = timetable.local_plan.organisations[0].reference
            else:
                model.organisation = "government-organisation:D1342"
        data.append(model.model_dump(by_alias=True))

    output = _to_csv(data, LocalPlanTimetableModel)
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


def _to_legacy_timetable(timetable):
    events = []
    for index, (key, value) in enumerate(timetable.event_data.items()):
        data = {}
        event_date = _collect_iso_date_fields(timetable.event_data, key)
        if not event_date or event_date == "--":
            continue
        kebabbed_key = key.replace("_", "-")
        ref = f"{timetable.reference}-{kebabbed_key}"
        data["reference"] = f"{ref}-{index}"
        data["event-date"] = event_date
        data["local-plan"] = timetable.local_plan.reference
        data["notes"] = value.get("notes")
        data["description"] = timetable.description or ""
        data["local-plan-event"] = kebabbed_key
        data["entry-date"] = timetable.entry_date
        data["start-date"] = timetable.start_date
        data["end-date"] = timetable.end_date
        data["organisation"] = ""
        data["name"] = ""
        events.append(data)
    return events


def _collect_iso_date_fields(event_data, key):
    if key == "notes":
        return ""
    try:
        dates = event_data.get(key, None)
        if dates is None:
            return None
        date_parts = []
        if dates.get("year", None):
            date_parts.append(dates["year"])
        if dates.get("month", None):
            date_parts.append(dates["month"])
        if dates.get("day", None):
            date_parts.append(dates["day"])
        return "-".join(date_parts)
    except Exception as e:
        print(f"Error collecting ISO date fields for key {key}: {e}")
        return None
