from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, url_for

from application.blueprints.timetable.forms import EventForm
from application.extensions import db
from application.models import (
    LocalPlan,
    LocalPlanEventType,
    LocalPlanTimetable,
    Organisation,
)
from application.utils import login_required

timetable = Blueprint(
    "timetable",
    __name__,
    url_prefix="/local-plan/<string:local_plan_reference>/timetable",
)


@timetable.route(
    "/add",
    methods=["GET", "POST"],
)
@login_required
def add(local_plan_reference):
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        return abort(404)

    action = url_for(
        "timetable.add",
        local_plan_reference=plan.reference,
    )
    action_text = "Add"

    form = EventForm()
    if plan.organisations:
        form.organisation.choices = [
            (organisation.organisation, organisation.name)
            for organisation in Organisation.query.order_by(Organisation.name).all()
        ]
    if plan.organisations and not form.is_submitted():
        if len(plan.organisations) == 1:
            form.organisation.data = plan.organisations[0].organisation

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": "Plans by organisation",
                "href": url_for("organisation.organisations"),
            },
            {
                "text": plan.name,
                "href": url_for("local_plan.get_plan", reference=plan.reference),
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
        local_plan_event = form.local_plan_event.data
        local_plan_event_type = LocalPlanEventType.query.get(
            local_plan_event.replace("_", "-")
        )
        if local_plan_event_type is None:
            abort(404)
        reference = (
            f"{plan.reference}-{local_plan_event_type.reference}-{len(plan.timetable)}"
        )
        local_plan_timetable = LocalPlanTimetable(
            reference=reference,
            event_date=event_date,
            local_plan_event=local_plan_event_type.reference,
            notes=form.notes.data,
        )
        plan.timetable.append(local_plan_timetable)
        if form.organisation.data:
            local_plan_timetable.organisation = form.organisation.data
        db.session.add(plan)
        db.session.add(local_plan_timetable)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=local_plan_reference))

    return render_template(
        "timetable/event-form.html",
        form=form,
        local_plan=plan,
        breadcrumbs=breadcrumbs,
        action=action,
        action_text=action_text,
    )


@timetable.route(
    "/<string:timetable_reference>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit(local_plan_reference, timetable_reference):
    timetable = LocalPlanTimetable.query.get(timetable_reference)
    if timetable is None:
        return abort(404)

    form = EventForm(obj=timetable)

    action = url_for(
        "timetable.edit",
        local_plan_reference=local_plan_reference,
        timetable_reference=timetable_reference,
    )
    action_text = "Edit"

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": "Plans by organisation",
                "href": url_for("organisation.organisations"),
            },
            {
                "text": timetable.local_plan.name,
                "href": url_for(
                    "local_plan.get_plan", reference=timetable.local_plan.reference
                ),
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
        local_plan_event = form.local_plan_event.data
        local_plan_event_type = LocalPlanEventType.query.get(
            local_plan_event.replace("_", "-")
        )
        timetable.event_date = event_date
        timetable.local_plan_event = local_plan_event_type.reference
        timetable.notes = form.notes.data
        timetable.organisation = (
            form.organisation.data if form.organisation.data else None
        )
        db.session.add(timetable)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=local_plan_reference))

    return render_template(
        "timetable/event-form.html",
        form=form,
        local_plan=timetable.local_plan,
        breadcrumbs=breadcrumbs,
        action=action,
        action_text=action_text,
    )


@timetable.route(
    "/<string:timetable_reference>/remove",
    methods=["GET"],
)
@login_required
def remove(local_plan_reference, timetable_reference):
    timetable = LocalPlanTimetable.query.get(timetable_reference)
    if timetable is None:
        return abort(404)
    timetable.end_date = datetime.now()
    db.session.add(timetable)
    db.session.commit()
    return redirect(url_for("local_plan.get_plan", reference=local_plan_reference))
