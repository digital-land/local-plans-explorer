from flask import Blueprint, abort, redirect, render_template, url_for

from application.blueprints.timetable.forms import EventForm
from application.extensions import db
from application.models import (
    EventCategory,
    LocalPlanEvent,
    LocalPlanEventType,
    LocalPlanTimetable,
)
from application.utils import login_required

timetable = Blueprint(
    "timetable",
    __name__,
    url_prefix="/local-plan/<string:local_plan_reference>/timetable",
)


@timetable.route("/<string:timetable_reference>")
def index(local_plan_reference, timetable_reference):
    timetable = LocalPlanTimetable.query.filter(
        LocalPlanTimetable.local_plan == local_plan_reference,
        LocalPlanTimetable.reference == timetable_reference,
    ).one_or_none()
    if timetable is None:
        abort(404)
    timeline_data = timetable.timeline()
    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": "Plans by organisation",
                "href": url_for("organisation.organisations"),
            },
            {
                "text": timetable.local_plan_obj.name,
                "href": url_for("local_plan.get_plan", reference=local_plan_reference),
            },
            {"text": "Local plan events timeline"},
        ]
    }

    return render_template(
        "timetable/index.html",
        timetable=timetable,
        timeline_data=timeline_data,
        breadcrumbs=breadcrumbs,
    )


@timetable.route("/<string:timetable_reference>/event/<string:event_reference>")
@login_required
def timetable_event(local_plan_reference, timetable_reference, event_reference):
    event = LocalPlanEvent.query.get(event_reference)
    if event is None:
        return abort(404)
    return event.name


@timetable.route("/<string:timetable_reference>/<event_category:event_category>")
@login_required
def timetable_events(local_plan_reference, timetable_reference, event_category):
    timetable = LocalPlanTimetable.query.filter(
        LocalPlanTimetable.local_plan == local_plan_reference,
        LocalPlanTimetable.reference == timetable_reference,
    ).one_or_none()

    if timetable is None:
        return abort(404)

    return timetable.events


@timetable.route(
    "/<string:timetable_reference>/event/add",
    methods=["GET", "POST"],
)
@login_required
def add_event(local_plan_reference, timetable_reference):
    timetable = LocalPlanTimetable.query.get(timetable_reference)
    if timetable is None:
        return abort(404)

    action = url_for(
        "timetable.add_event",
        local_plan_reference=local_plan_reference,
        timetable_reference=timetable_reference,
    )
    action_text = "Add"

    form = EventForm()

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": "Plans by organisation",
                "href": url_for("organisation.organisations"),
            },
            {
                "text": timetable.local_plan_obj.name,
                "href": url_for("local_plan.get_plan", reference=local_plan_reference),
            },
            {"text": "Add event"},
        ]
    }

    if form.validate_on_submit():
        event_date = form.event_date.data.get("year")
        if form.event_date.data.get("month"):
            month = form.event_date.data.get("month")
            event_date += f"-{int(month):02d}"
        if form.event_date.data.get("day"):
            day = form.event_date.data.get("day")
            event_date += f"-{int(day):02d}"
        event_type = form.event_type.data
        local_plan_event_type = LocalPlanEventType.query.get(
            event_type.replace("_", "-")
        )
        if local_plan_event_type is None:
            abort(404)
        reference = f"{timetable.reference}-{len(timetable.events)}"
        local_plan_event = LocalPlanEvent(
            reference=reference,
            event_date=event_date,
            event_category=EventCategory.TIMETABLE_PUBLISHED.name,
            local_plan_event_type_reference=local_plan_event_type.reference,
            notes=form.notes.data,
        )
        timetable.events.append(local_plan_event)
        db.session.add(timetable)
        db.session.add(local_plan_event)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=local_plan_reference))

    return render_template(
        "timetable/event-form.html",
        form=form,
        local_plan=timetable.local_plan_obj,
        breadcrumbs=breadcrumbs,
        action=action,
        action_text=action_text,
    )


@timetable.route(
    "/<string:timetable_reference>/event/<string:event_reference>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_event(local_plan_reference, timetable_reference, event_reference):
    event = LocalPlanEvent.query.get(event_reference)
    if event is None:
        return abort(404)

    form = EventForm(obj=event)

    action = url_for(
        "timetable.edit_event",
        local_plan_reference=local_plan_reference,
        timetable_reference=timetable_reference,
        event_reference=event_reference,
    )
    action_text = "Edit"

    event_timetable = LocalPlanTimetable.query.get(event.local_plan_timetable)
    if event_timetable is None:
        return abort(404)

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": "Plans by organisation",
                "href": url_for("organisation.organisations"),
            },
            {
                "text": event_timetable.local_plan_obj.name,
                "href": url_for("local_plan.get_plan", reference=local_plan_reference),
            },
            {"text": "Edit event"},
        ]
    }

    if form.validate_on_submit():
        event_date = form.event_date.data.get("year")
        if form.event_date.data.get("month"):
            month = form.event_date.data.get("month")
            event_date += f"-{int(month):02d}"
        if form.event_date.data.get("day"):
            day = form.event_date.data.get("day")
            event_date += f"-{int(day):02d}"
        event_type = form.event_type.data
        event_type = form.event_type.data
        local_plan_event_type = LocalPlanEventType.query.get(
            event_type.replace("_", "-")
        )
        event.event_date = event_date
        event.local_plan_event_type_reference = local_plan_event_type.reference
        event.notes = form.notes.data
        db.session.add(event)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=local_plan_reference))

    return render_template(
        "timetable/event-form.html",
        form=form,
        local_plan=event_timetable.local_plan_obj,
        breadcrumbs=breadcrumbs,
        action=action,
        action_text=action_text,
    )
