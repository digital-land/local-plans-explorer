from flask import Blueprint, abort, redirect, render_template, request, url_for

from application.blueprints.timetable.forms import get_event_form
from application.extensions import db
from application.models import (
    EventCategory,
    LocalPlan,
    LocalPlanEvent,
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
    return render_template(
        "timetable/index.html", timetable=timetable, timeline_data=timeline_data
    )


@timetable.route(
    "/event-type/<event_category:event_category>/add", methods=["GET", "POST"]
)
@login_required
def add_new_timetable_event(local_plan_reference, event_category):
    plan = LocalPlan.query.get(local_plan_reference)
    estimated = True if event_category.value.lower().startswith("estimated") else False
    form = get_event_form(event_category)

    redirect_url = _redirect_url_category_exists(plan, event_category)
    if redirect_url is not None:
        return redirect(redirect_url)

    if request.method == "POST":
        if form.validate():
            # Check if form is completely empty
            if form.is_completely_empty():
                # Skip to next stage without creating any objects
                continue_url = _skip_and_continue_url(
                    local_plan_reference, event_category
                )
                return redirect(continue_url)

            # Otherwise create event as normal
            if plan.timetable is None:
                plan.timetable = LocalPlanTimetable(
                    reference=f"{plan.reference}-timetable",
                    name=f"{plan.name} timetable",
                    local_plan=plan.reference,
                    events=[],
                )
            event_reference = f"{plan.timetable.reference}-{len(plan.timetable.events)}"
            if hasattr(form, "notes"):
                notes = form.notes.data
            else:
                notes = None

            # Only store validated data
            validated_data = {}
            for field in form:
                if field.name != "csrf_token":
                    if isinstance(field.data, dict):
                        # For date fields, only include if they passed validation
                        if any(field.data.values()):
                            validated_data[field.name] = field.data
                    else:
                        validated_data[field.name] = field.data

            event = LocalPlanEvent(
                reference=event_reference,
                event_category=event_category,
                event_data=validated_data,
                notes=notes,
            )
            plan.timetable.events.append(event)
            db.session.add(event)
            db.session.add(plan)
            db.session.commit()
            return redirect(
                url_for(
                    "timetable.timetable_event",
                    local_plan_reference=plan.reference,
                    timetable_reference=plan.timetable.reference,
                    event_reference=event.reference,
                )
            )

    if estimated:
        event_category_title = event_category.value.replace("Estimated", "").strip()
    else:
        event_category_title = event_category.value

    include_plan_published = _include_plan_published(plan, event_category)

    action_url = url_for(
        "timetable.add_new_timetable_event",
        local_plan_reference=local_plan_reference,
        event_category=event_category,
    )
    skip_url = _skip_and_continue_url(local_plan_reference, event_category)
    if event_category in [
        EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION,
        EventCategory.PLANNING_INSPECTORATE_FINDINGS,
    ]:
        skip_text = "Return to local plan"
    else:
        skip_text = "Skip to next event"

    return render_template(
        "timetable/event-form.html",
        plan=plan,
        form=form,
        estimated=estimated,
        action_url=action_url,
        event_category=event_category,
        event_category_title=event_category_title,
        include_plan_published=include_plan_published,
        skip_url=skip_url,
        skip_text=skip_text,
    )


@timetable.route("/<string:timetable_reference>/event/<string:event_reference>")
@login_required
def timetable_event(local_plan_reference, timetable_reference, event_reference):
    event = LocalPlanEvent.query.get(event_reference)
    if event is None:
        return abort(404)
    timetable = LocalPlanTimetable.query.get(timetable_reference)
    if timetable is None:
        return abort(404)
    event_category = event.event_category
    if "estimated" in event_category.value.lower():
        estimated = True
    else:
        estimated = False
    event_category_title = event_category.value.replace("Estimated", "").strip()

    if event_category in [
        EventCategory.ESTIMATED_REGULATION_18,
        EventCategory.ESTIMATED_REGULATION_19,
        EventCategory.REGULATION_18,
        EventCategory.REGULATION_19,
    ]:
        return _render_consultation_event_page(
            event, event_category, estimated, event_category_title
        )
    elif event_category == EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION:
        return _render_estimated_examination_and_adoption_event_page(
            event, event_category, estimated, event_category_title
        )
    elif event_category in [
        EventCategory.PLANNING_INSPECTORATE_EXAMINATION,
        EventCategory.PLANNING_INSPECTORATE_FINDINGS,
    ]:
        continue_url = _get_save_and_continue_url(local_plan_reference, event_category)
        return render_template(
            "timetable/pins-exam-and-findings.html",
            events=[event],
            timetable=timetable,
            estimated=estimated,
            event_category=event_category,
            event_category_title=event_category_title,
            continue_url=continue_url,
        )
    else:
        return redirect(url_for("local_plan.get_plan", reference=local_plan_reference))


@timetable.route("/<string:timetable_reference>/<event_category:event_category>")
@login_required
def timetable_events(local_plan_reference, timetable_reference, event_category):
    timetable = LocalPlanTimetable.query.filter(
        LocalPlanTimetable.local_plan == local_plan_reference,
        LocalPlanTimetable.reference == timetable_reference,
    ).one_or_none()

    if timetable is None:
        return abort(404)

    estimated = True if "estimated" in event_category.value.lower() else False

    if event_category in [
        EventCategory.ESTIMATED_REGULATION_18,
        EventCategory.ESTIMATED_REGULATION_19,
        EventCategory.REGULATION_18,
        EventCategory.REGULATION_19,
    ]:
        events = timetable.get_events_by_category(event_category)
        event_category_title = event_category.value.replace("Estimated", "").strip()
        plan_reference = timetable.local_plan
        continue_url = _get_save_and_continue_url(plan_reference, event_category)
        return render_template(
            "timetable/consultations.html",
            plan=timetable.local_plan_obj,
            timetable=timetable,
            events=events,
            estimated=estimated,
            event_category=event_category,
            event_category_title=event_category_title,
            continue_url=continue_url,
        )
    elif event_category == EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION:
        event_category_title = event_category.value
        events = timetable.get_events_by_category(event_category)
        if events and len(events) == 1:
            event = events[0]
            return _render_estimated_examination_and_adoption_event_page(
                event, event_category, estimated, event_category_title
            )
        else:
            return abort(404)
    elif event_category in [
        EventCategory.PLANNING_INSPECTORATE_EXAMINATION,
        EventCategory.PLANNING_INSPECTORATE_FINDINGS,
    ]:
        event_category_title = event_category.value
        events = timetable.get_events_by_category(event_category)
        continue_url = _get_save_and_continue_url(local_plan_reference, event_category)
        if events:
            return render_template(
                "timetable/pins-exam-and-findings.html",
                events=events,
                timetable=timetable,
                estimated=estimated,
                event_category=event_category,
                event_category_title=event_category_title,
                continue_url=continue_url,
                index=True,
            )
        else:
            return abort(404)
    else:
        return abort(404)


@timetable.route(
    "/<string:timetable_reference>/event-type/<event_category:event_category>/add",
    methods=["GET", "POST"],
)
@login_required
def add_event_to_timetable(local_plan_reference, timetable_reference, event_category):
    timetable = LocalPlanTimetable.query.get(timetable_reference)
    if timetable is None:
        return abort(404)
    estimated = True if event_category.value.lower().startswith("estimated") else False
    form = get_event_form(event_category)

    if form.validate_on_submit():
        if form.is_completely_empty():
            # Skip to next stage without creating any objects
            continue_url = _skip_and_continue_url(local_plan_reference, event_category)
            return redirect(continue_url)

        if timetable.events is None:
            timetable.events = []
        reference = f"{timetable.reference}-{len(timetable.events)}"
        if hasattr(form, "notes"):
            notes = form.notes.data
        else:
            notes = None

        # Only store validated data
        validated_data = {}
        for field in form:
            if field.name != "csrf_token":
                if isinstance(field.data, dict):
                    # For date fields, only include if they passed validation
                    if any(field.data.values()):
                        validated_data[field.name] = field.data
                else:
                    validated_data[field.name] = field.data

        event = LocalPlanEvent(
            reference=reference,
            event_category=event_category,
            event_data=validated_data,
            notes=notes,
        )
        timetable.events.append(event)
        db.session.add(event)
        db.session.add(timetable)
        db.session.commit()
        return redirect(
            url_for(
                "timetable.timetable_event",
                local_plan_reference=timetable.local_plan,
                timetable_reference=timetable.reference,
                event_reference=event.reference,
            )
        )

    if estimated:
        event_category_title = event_category.value.replace("Estimated", "").strip()
    else:
        event_category_title = event_category.value

    include_plan_published = _include_plan_published(
        timetable.local_plan_obj, event_category
    )

    action_url = url_for(
        "timetable.add_event_to_timetable",
        local_plan_reference=local_plan_reference,
        timetable_reference=timetable_reference,
        event_category=event_category,
    )
    skip_url = _skip_and_continue_url(local_plan_reference, event_category)
    if event_category in [
        EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION,
        EventCategory.PLANNING_INSPECTORATE_FINDINGS,
    ]:
        skip_text = "Return to local plan"
    else:
        skip_text = "Skip to next event"

    return render_template(
        "timetable/event-form.html",
        plan=timetable.local_plan_obj,
        form=form,
        estimated=estimated,
        action_url=action_url,
        event_category=event_category,
        event_category_title=event_category_title,
        include_plan_published=include_plan_published,
        skip_url=skip_url,
        skip_text=skip_text,
    )


@timetable.route(
    "/<string:timetable_reference>/event/<string:event_reference>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_timetable_event(local_plan_reference, timetable_reference, event_reference):
    event = LocalPlanEvent.query.get(event_reference)
    if event is None:
        return abort(404)

    include_plan_published = _is_first_event_of_category(event)

    form = get_event_form(event.event_category, obj=event.event_data)

    if form.validate_on_submit():
        event.event_data = form.data
        db.session.add(event)
        db.session.commit()
        return redirect(
            url_for(
                "timetable.timetable_event",
                local_plan_reference=local_plan_reference,
                timetable_reference=timetable_reference,
                event_reference=event.reference,
            )
        )

    action_url = url_for(
        "timetable.edit_timetable_event",
        local_plan_reference=local_plan_reference,
        timetable_reference=timetable_reference,
        event_reference=event_reference,
    )

    include_plan_published = _is_first_event_of_category(event)
    estimated = True if "estimated" in event.event_category.value.lower() else False

    if estimated:
        event_category_title = event.event_category.value.replace(
            "Estimated", ""
        ).strip()
    else:
        event_category_title = event.event_category.value

    return render_template(
        "timetable/event-form.html",
        form=form,
        event=event,
        action_url=action_url,
        plan=event.timetable.local_plan_obj,
        timetable=event.timetable,
        event_category=event.event_category,
        include_plan_published=include_plan_published,
        estimated=estimated,
        event_category_title=event_category_title,
    )


def _render_consultation_event_page(
    event: LocalPlanEvent, event_category, estimated, event_category_title
):
    edit_url = url_for(
        "timetable.edit_timetable_event",
        local_plan_reference=event.timetable.local_plan,
        timetable_reference=event.timetable.reference,
        event_reference=event.reference,
    )
    plan_reference = event.timetable.local_plan
    continue_url = _get_save_and_continue_url(plan_reference, event_category)

    return render_template(
        "timetable/consultation.html",
        event=event,
        estimated=estimated,
        event_category=event_category,
        event_category_title=event_category_title,
        edit_url=edit_url,
        continue_url=continue_url,
    )


def _render_estimated_examination_and_adoption_event_page(
    event, event_category, estimated, event_category_title
):
    edit_url = url_for(
        "timetable.edit_timetable_event",
        local_plan_reference=event.timetable.local_plan,
        timetable_reference=event.timetable.reference,
        event_reference=event.reference,
    )

    return render_template(
        "timetable/estimated-examination-and-adoption.html",
        event=event,
        estimated=estimated,
        event_category=event_category,
        event_category_title=event_category_title,
        edit_url=edit_url,
    )


def _redirect_url_category_exists(plan, event_category):
    if (
        event_category == EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION
        and plan.timetable
    ):
        events = plan.timetable.get_events_by_category(
            EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION
        )
        if events and len(events) == 1:
            return url_for(
                "timetable.timetable_event",
                local_plan_reference=plan.reference,
                timetable_reference=plan.timetable.reference,
                event_reference=events[0].reference,
            )
    elif plan.timetable:
        events = plan.timetable.get_events_by_category(event_category)
        if events:
            return url_for(
                "timetable.timetable_events",
                local_plan_reference=plan.reference,
                timetable_reference=plan.timetable.reference,
                event_category=event_category,
            )

    return None


def _is_first_event_of_category(event):
    earlier_events = LocalPlanEvent.query.filter(
        LocalPlanEvent.timetable == event.timetable,
        LocalPlanEvent.event_category == event.event_category,
        LocalPlanEvent.created_date < event.created_date,
    ).all()
    return True if not earlier_events else False


def _skip_and_continue_url(
    plan_reference: str, event_category: EventCategory
) -> str | None:
    """Get URL for skipping to next stage's timetable events view"""
    next_category = _get_next_category(event_category)
    if next_category is None:
        return url_for("local_plan.get_plan", reference=plan_reference)

    return url_for(
        "timetable.add_new_timetable_event",
        local_plan_reference=plan_reference,
        event_category=next_category,
    )


def _get_next_category(event_category: EventCategory) -> EventCategory | None:
    """Get the next event category in the sequence"""
    match event_category:
        case EventCategory.ESTIMATED_REGULATION_18:
            return EventCategory.ESTIMATED_REGULATION_19
        case EventCategory.ESTIMATED_REGULATION_19:
            return EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION
        case EventCategory.REGULATION_18:
            return EventCategory.REGULATION_19
        case EventCategory.REGULATION_19:
            return EventCategory.PLANNING_INSPECTORATE_EXAMINATION
        case EventCategory.PLANNING_INSPECTORATE_EXAMINATION:
            return EventCategory.PLANNING_INSPECTORATE_FINDINGS
        case _:
            return None


def _get_save_and_continue_url(
    plan_reference: str, event_category: EventCategory
) -> str | None:
    """Get URL for continuing after saving an event"""
    next_category = _get_next_category(event_category)
    if next_category is None:
        return url_for("local_plan.get_plan", reference=plan_reference)

    return url_for(
        "timetable.add_new_timetable_event",
        local_plan_reference=plan_reference,
        event_category=next_category,
    )


def _include_plan_published(plan, event_category):
    if event_category in [
        EventCategory.PLANNING_INSPECTORATE_EXAMINATION,
        EventCategory.PLANNING_INSPECTORATE_FINDINGS,
    ]:
        return False
    if plan.timetable and plan.timetable.event_category_progress(event_category) in [
        "started",
        "completed",
    ]:
        return False
    return True
