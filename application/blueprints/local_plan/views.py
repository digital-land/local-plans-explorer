import json
from datetime import datetime

import geopandas as gpd
from flask import Blueprint, abort, redirect, render_template, request, url_for
from slugify import slugify

from application.blueprints.document.forms import DocumentForm
from application.blueprints.local_plan.forms import ConsultationForm, LocalPlanForm
from application.extensions import db
from application.models import (
    CandidateDocument,
    DocumentStatus,
    EventCategory,
    LocalPlan,
    LocalPlanBoundary,
    LocalPlanDocument,
    LocalPlanDocumentType,
    LocalPlanEvent,
    LocalPlanTimetable,
    Organisation,
    Status,
)
from application.utils import (
    combine_geographies,
    generate_random_string,
    get_centre_and_bounds,
    login_required,
    populate_object,
)

local_plan = Blueprint("local_plan", __name__, url_prefix="/local-plan")


@local_plan.route("/")
def index():
    plans = LocalPlan.query.all()
    return render_template("local_plan/index.html", plans=plans)


@local_plan.route("/<string:reference>")
def get_plan(reference):
    plan = LocalPlan.query.get(reference)
    if plan is None:
        return abort(404)

    if plan.boundary and plan.boundary.geojson:
        coords, bounding_box = get_centre_and_bounds(plan.boundary.geojson)
        geography = {
            "name": plan.name,
            "features": plan.boundary.geojson,
            "coords": coords,
            "bounding_box": bounding_box,
            "reference": plan.boundary.reference,
        }
    else:
        geography = None
        bounding_box = None

    document_counts = _get_document_counts(plan.documents)

    stage_urls = {}
    for event_category in [
        EventCategory.ESTIMATED_REGULATION_18,
        EventCategory.ESTIMATED_REGULATION_19,
    ]:
        if plan.timetable and plan.timetable.event_category_progress(
            event_category
        ) in [
            "started",
            "completed",
        ]:
            stage_urls[event_category] = url_for(
                "local_plan.timetable_events",
                reference=plan.reference,
                timetable_reference=plan.timetable.reference,
                event_category=event_category,
            )
        else:
            stage_urls[event_category] = url_for(
                "local_plan.add_timetable_event",
                reference=plan.reference,
                event_category=event_category,
            )

    return render_template(
        "local_plan/plan.html",
        plan=plan,
        geography=geography,
        bounding_box=bounding_box,
        document_counts=document_counts,
        event_category=EventCategory,
        stage_urls=stage_urls,
    )


@local_plan.route("/add", methods=["GET", "POST"])
@login_required
def add():
    form = LocalPlanForm()
    if request.args.get("organisation"):
        organisation = request.args.get("organisation")
        org = Organisation.query.get_or_404(organisation)
    else:
        org = None
    orgs = (
        Organisation.query.filter(Organisation.end_date.is_(None))
        .order_by(Organisation.name)
        .all()
    )
    organisation_choices = [(org.organisation, org.name) for org in orgs]
    form.organisations.choices = [(" ", " ")] + organisation_choices
    if org is not None:
        form.organisations.default = org.organisation
        form.process()

    form.status.choices = [(s.name, s.value) for s in Status if s != Status.EXPORTED]

    if form.validate_on_submit():
        reference = _make_reference(form)
        plan = LocalPlan(
            reference=reference,
        )
        populate_object(form, plan)

        db.session.add(plan)
        db.session.commit()
        return redirect(url_for("local_plan.add_geography", reference=plan.reference))

    return render_template("local_plan/add.html", form=form, organisation=org)


@local_plan.route("/<string:reference>/edit", methods=["GET", "POST"])
@login_required
def edit(reference):
    plan = LocalPlan.query.get(reference)
    if plan is None:
        return abort(404)

    organisation__string = ";".join([org.organisation for org in plan.organisations])

    del plan.organisations

    form = LocalPlanForm(obj=plan)

    if not form.organisations.data:
        form.organisations.data = organisation__string

    organisations = (
        Organisation.query.filter(Organisation.end_date.is_(None))
        .order_by(Organisation.name)
        .all()
    )
    organisation_choices = [(org.organisation, org.name) for org in organisations]
    form.organisations.choices = organisation_choices

    form.status.choices = [(s.name, s.value) for s in Status if s != Status.EXPORTED]

    if form.validate_on_submit():
        plan = populate_object(form, plan)
        db.session.add(plan)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=plan.reference))

    return render_template("local_plan/edit.html", plan=plan, form=form)


@local_plan.route("/archived")
def archived_plans():
    if request.args.get("organisation"):
        organisation = request.args.get("organisation")
        plans = (
            LocalPlan.query.filter(LocalPlan.status == Status.NOT_FOR_PLATFORM)
            .filter(
                LocalPlan.organisations.any(Organisation.organisation == organisation)
            )
            .all()
        )
    else:
        plans = LocalPlan.query.filter(
            LocalPlan.status == Status.NOT_FOR_PLATFORM
        ).all()
    return render_template("local_plan/archived.html", plans=plans)


@local_plan.route("/<string:reference>/find-documents")
@login_required
def find_documents(reference):
    from application.scraping import extract_links_from_page

    plan = LocalPlan.query.get(reference)
    if plan is None:
        abort(404)

    document_types = [doc.name for doc in LocalPlanDocumentType.query.all()]
    document_links = extract_links_from_page(
        plan.documentation_url, plan, document_types
    )

    for link in document_links:
        document_url = link["document_url"]
        existing_doc = LocalPlanDocument.query.filter(
            LocalPlanDocument.document_url == document_url,
            LocalPlanDocument.local_plan == plan.reference,
        ).one_or_none()

        documents = []
        if existing_doc is None:
            existing_candidate = CandidateDocument.query.filter(
                CandidateDocument.document_url == document_url,
                CandidateDocument.local_plan == plan.reference,
            ).one_or_none()
            if existing_candidate is None:
                doc_type = link.pop("document_type", None)
                if doc_type is not None:
                    doc_type = LocalPlanDocumentType.query.filter(
                        LocalPlanDocumentType.name == doc_type
                    ).one_or_none()
                candidate_document = CandidateDocument(**link)
                candidate_document.document_type = (
                    doc_type.reference if doc_type else None
                )
                db.session.add(candidate_document)
                db.session.commit()

    documents = CandidateDocument.query.filter(
        CandidateDocument.local_plan == plan.reference,
        CandidateDocument.status.is_(None),
    ).all()

    return render_template(
        "local_plan/find-documents.html", plan=plan, documents=documents
    )


@local_plan.route("/<string:reference>/accept/<string:doc_id>", methods=["GET", "POST"])
@login_required
def accept_document(reference, doc_id):
    plan = LocalPlan.query.get(reference)
    if plan is None:
        abort(404)

    candidate = CandidateDocument.query.get(doc_id)

    if candidate is None:
        abort(404)

    document_types = [
        doc_type.reference
        for doc_type in LocalPlanDocumentType.query.filter(
            LocalPlanDocumentType.reference == candidate.document_type
        ).all()
    ]

    form = DocumentForm(obj=candidate)
    organisations = (
        Organisation.query.filter(Organisation.end_date.is_(None))
        .order_by(Organisation.name)
        .all()
    )
    organisation_choices = [(org.organisation, org.name) for org in organisations]
    form.organisations.choices = [(" ", " ")] + organisation_choices
    organisation__string = ";".join([org.organisation for org in plan.organisations])
    form.organisations.data = organisation__string
    form.document_types.choices = [
        (dt.reference, dt.name) for dt in LocalPlanDocumentType.query.all()
    ]
    form.document_types.data = document_types

    if form.validate_on_submit():
        reference = slugify(form.name.data)
        doc = LocalPlanDocument(
            reference=reference,
            local_plan=plan.reference,
            name=form.name.data,
            documentation_url=form.documentation_url.data,
            document_url=form.document_url.data,
            organisations=plan.organisations,
            document_types=document_types if document_types else None,
        )
        candidate.status = DocumentStatus.ACCEPT
        db.session.add(doc)
        db.session.add(candidate)
        db.session.commit()

        unprocessed = CandidateDocument.query.filter(
            CandidateDocument.local_plan == plan.reference,
            CandidateDocument.status.is_(None),
        ).all()

        if unprocessed:
            return redirect(
                url_for("local_plan.find_documents", reference=plan.reference)
            )
        return redirect(url_for("local_plan.get_plan", reference=plan.reference))

    return render_template(
        "document/add.html",
        plan=plan,
        form=form,
        action=url_for(
            "local_plan.accept_document", reference=plan.reference, doc_id=candidate.id
        ),
    )


@local_plan.route("/<string:reference>/reject/<string:doc_id>")
@login_required
def reject_document(reference, doc_id):
    plan = LocalPlan.query.get(reference)
    if plan is None:
        abort(404)

    candidate = CandidateDocument.query.get(doc_id)

    if candidate is None:
        abort(404)

    candidate.status = DocumentStatus.REJECT
    db.session.add(candidate)
    db.session.commit()

    unprocessed = CandidateDocument.query.filter(
        CandidateDocument.local_plan == plan.reference,
        CandidateDocument.status.is_(None),
    ).all()

    if unprocessed:
        return redirect(url_for("local_plan.find_documents", reference=plan.reference))

    return redirect(url_for("local_plan.get_plan", reference=plan.reference))


@local_plan.route("/<string:reference>/geography/add", methods=["GET", "POST"])
@login_required
def add_geography(reference):
    plan = LocalPlan.query.get(reference)
    if plan is None:
        return abort(404)

    if request.method == "POST":
        geography_provided = request.form.get("geography-provided", None)
        if geography_provided is not None:
            geographies = [
                _make_collection(org.geojson)
                for org in plan.organisations
                if org.geojson is not None
            ]

            if len(plan.organisations) == 1:
                reference = (
                    plan.organisations[0].statistical_geography
                    if plan.organisations[0].geojson is not None
                    else None
                )
                geography_type = "planning-authority-district"
            else:
                reference = "-".join(
                    [
                        org.statistical_geography
                        for org in plan.organisations
                        if org.geojson is not None
                    ]
                )
                geography_type = "combined-planning-authority-district"

            geojson = combine_geographies(geographies)
            boundary = LocalPlanBoundary.query.get(reference)
            if boundary is None:
                boundary = LocalPlanBoundary(
                    reference=reference,
                    geojson=geojson,
                    plan_boundary_type=geography_type,
                )
            plan.boundary = boundary
            boundary.local_plans.append(plan)
            db.session.add(plan)
            db.session.add(boundary)
            db.session.commit()
            return redirect(url_for("local_plan.get_plan", reference=plan.reference))
        else:
            return redirect(url_for("local_plan.get_plan", reference=plan.reference))
    # Don't include file upload at this stage
    # else:
    #     if "fileUpload" in request.files:
    #         file = request.files["fileUpload"]
    #         reference = (
    #             request.form["designated-plan-area"].replace(" ", "-").lower()
    #         )
    #         if file and _allowed_file(file.filename):
    #             with TemporaryDirectory() as tempdir:
    #                 filename = secure_filename(file.filename)
    #                 shapefile_path = os.path.join(tempdir, filename)
    #                 file.save(shapefile_path)
    #                 gdf = gpd.read_file(shapefile_path)
    #                 geojson = gdf.to_crs(epsg="4326").to_json()
    #                 boundary = LocalPlanBoundary(
    #                     reference=reference,
    #                     geojson=json.loads(geojson),
    #                     plan_boundary_type="combined-planning-authority-district"
    #                 )
    #                 plan.geography = boundary
    #                 boundary.local_plans.append(plan)
    #                 db.session.add(plan)
    #                 db.session.add(boundary)
    #                 db.session.commit()
    #
    #         return redirect(url_for("development_plan.plan", reference=plan.reference))
    #

    geographies = []
    references = []
    missing_geographies = []

    for org in plan.organisations:
        if org.geometry is not None and org.geojson is not None:
            references.append(org.statistical_geography)
            geographies.append(_make_collection(org.geojson))
        else:
            missing_geographies.append(org)
    if geographies:
        geography = combine_geographies(geographies)
        geography_reference = ":".join(references)
        gdf = gpd.read_file(json.dumps(geography), driver="GeoJSON")
        coords = {"lat": gdf.centroid.y[0], "long": gdf.centroid.x[0]}
        bounding_box = list(gdf.total_bounds)
    else:
        geography = None
        geography_reference = None
        coords = None
        bounding_box = None
    return render_template(
        "local_plan/choose-geography.html",
        plan=plan,
        geography=geography,
        geography_reference=geography_reference,
        coords=coords,
        geographies=geographies,
        missing_geographies=missing_geographies,
        bounding_box=bounding_box,
    )


@local_plan.route(
    "/<string:reference>/timetable/<string:timetable_reference>/event/<string:event_id>"
)
@login_required
def timetable_event(reference, timetable_reference, event_id):
    event = LocalPlanEvent.query.get(event_id)
    if event is None:
        return abort(404)
    event_category = event.event_category
    if "estimated" in event_category.value.lower():
        estimated = True
    else:
        estimated = False
    event_category_title = event_category.value.replace("Estimated", "").strip()

    if "draft_local_plan_published" in event.event_data:
        draft_plan_published = _collect_date_fields(
            event.event_data, "draft_local_plan_published"
        )
    else:
        draft_plan_published = None

    consultation_start = _collect_date_fields(event.event_data, "consultation_start")
    consultation_end = _collect_date_fields(event.event_data, "consultation_end")
    consultation_covers = event.event_data.get("consultation_covers", None)

    edit_url = url_for(
        "local_plan.edit_timetable_event",
        reference=event.timetable.local_plan,
        timetable_reference=event.timetable.reference,
        event_id=event.id,
    )
    plan_reference = event.timetable.local_plan
    continue_url = _get_save_and_continue_url(plan_reference, event_category)

    return render_template(
        "local_plan/timetable-event.html",
        event=event,
        estimated=estimated,
        event_category=event_category,
        event_category_title=event_category_title,
        draft_plan_published=draft_plan_published,
        consultation_start=consultation_start,
        consultation_end=consultation_end,
        consultation_covers=consultation_covers,
        edit_url=edit_url,
        continue_url=continue_url,
    )


@local_plan.route(
    "/<string:reference>/timetable/<string:timetable_reference>/<event_category:event_category>"
)
@login_required
def timetable_events(reference, timetable_reference, event_category):
    timetable = LocalPlanTimetable.query.filter(
        LocalPlanTimetable.local_plan == reference,
        LocalPlanTimetable.reference == timetable_reference,
    ).one_or_none()

    if timetable is None:
        return abort(404)

    estimated = True if "estimated" in event_category.value.lower() else False

    events = timetable.get_events_by_category(event_category)

    events_data = _collate_events_data(events, event_category)

    event_category_title = event_category.value.replace("Estimated", "").strip()

    plan_reference = timetable.local_plan
    continue_url = _get_save_and_continue_url(plan_reference, event_category)

    return render_template(
        "local_plan/timetable-events.html",
        plan=timetable.local_plan,
        timetable=timetable,
        events=events,
        events_data=events_data,
        estimated=estimated,
        event_category=event_category,
        event_category_title=event_category_title,
        continue_url=continue_url,
    )


@local_plan.route(
    "/<string:reference>/<event_category:event_category>/add", methods=["GET", "POST"]
)
@login_required
def add_timetable_event(reference, event_category):
    plan = LocalPlan.query.get(reference)
    estimated = True if event_category.value.lower().startswith("estimated") else False
    form = _get_event_form(event_category=event_category)

    if form.validate_on_submit():
        event = LocalPlanEvent(event_category=event_category, event_data=form.data)
        if plan.timetable is not None:
            plan.timetable.events.append(event)
        else:
            plan.timetable = LocalPlanTimetable(
                reference=f"{plan.reference}-timetable",
                name=f"{plan.name} timetable",
                local_plan=plan.reference,
                events=[event],
            )
        db.session.add(event)
        db.session.add(plan)
        db.session.commit()
        return redirect(
            url_for(
                "local_plan.timetable_event",
                reference=plan.reference,
                timetable_reference=plan.timetable.reference,
                event_id=event.id,
            )
        )

    if estimated:
        event_category_title = event_category.value.replace("Estimated", "").strip()
    else:
        event_category_title = event_category.value

    if plan.timetable and plan.timetable.event_category_progress(event_category) in [
        "started",
        "completed",
    ]:
        include_draft_plan_published = False
    else:
        include_draft_plan_published = True

    action_url = url_for(
        "local_plan.add_timetable_event",
        reference=reference,
        event_category=event_category,
    )

    return render_template(
        "local_plan/timetable-event-form.html",
        plan=plan,
        form=form,
        estimated=estimated,
        action_url=action_url,
        event_category=event_category,
        event_category_title=event_category_title,
        include_draft_plan_published=include_draft_plan_published,
    )


@local_plan.route(
    "/<string:reference>/timetable/<string:timetable_reference>/event/<string:event_id>/edit",
    methods=["GET", "POST"],
)
@login_required
def edit_timetable_event(reference, timetable_reference, event_id):
    event = LocalPlanEvent.query.get(event_id)
    if event is None:
        return abort(404)

    form = _get_event_form(obj=event.event_data, event_category=event.event_category)

    if form.validate_on_submit():
        event.event_data = form.data
        db.session.add(event)
        db.session.commit()
        return redirect(
            url_for(
                "local_plan.timetable_event",
                reference=reference,
                timetable_reference=timetable_reference,
                event_id=event.id,
            )
        )

    action_url = url_for(
        "local_plan.edit_timetable_event",
        reference=reference,
        timetable_reference=timetable_reference,
        event_id=event_id,
    )

    include_draft_plan_published = _is_first_event_of_category(event)
    estimated = True if "estimated" in event.event_category.value.lower() else False

    return render_template(
        "local_plan/timetable-event-form.html",
        form=form,
        event=event,
        action_url=action_url,
        plan=event.timetable.local_plan_obj,
        timetable=event.timetable,
        event_category=event.event_category,
        include_draft_plan_published=include_draft_plan_published,
        estimated=estimated,
    )


def _get_document_counts(documents):
    counts = {}
    for status in Status:
        counts[status.value] = len([doc for doc in documents if doc.status == status])
    return counts


def _make_reference(form):
    reference = slugify(form.name.data)
    if LocalPlan.query.get(reference) is None:
        return reference

    reference = slugify(
        f"{reference}-{form.period_start_date.data}-{form.period_end_date.data}"
    )
    if LocalPlan.query.get(reference) is None:
        return reference

    reference = f"{reference}-{datetime.now().strftime('%Y-%m-%d')}"
    if LocalPlan.query.get(reference) is None:
        return reference

    return f"{reference}-{generate_random_string(6)}"


def _make_collection(geojson):
    if geojson["type"] == "Feature":
        return {"type": "FeatureCollection", "features": [geojson]}
    if geojson["type"] == "FeatureCollection":
        return geojson
    return {}


def _allowed_file(filename):
    from flask import current_app

    ALLOWED_EXTENSIONS = current_app.config["ALLOWED_EXTENSIONS"]
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _collect_date_fields(data, key):
    dates = data.get(key, None)
    if dates is None:
        return ""
    date_parts = []
    if dates.get("day", None):
        date_parts.append(dates["day"])
    if dates.get("month", None):
        date_parts.append(dates["month"])
    if dates.get("year", None):
        date_parts.append(dates["year"])
    return "/".join(date_parts)


def _collate_events_data(events, category):
    match category:
        case EventCategory.ESTIMATED_REGULATION_18 | EventCategory.ESTIMATED_REGULATION_19:
            return [
                {
                    "draft_local_plan_published": _collect_date_fields(
                        event.event_data, "draft_local_plan_published"
                    ),
                    "public_consultation_start": _collect_date_fields(
                        event.event_data, "consultation_start"
                    ),
                    "public_consultation_end": _collect_date_fields(
                        event.event_data, "consultation_end"
                    ),
                    "consultation_covers": event.event_data.get(
                        "consultation_covers", ""
                    ),
                    "event": event,
                }
                for event in events
            ]
        case _:
            return None


def _is_first_event_of_category(event):
    earlier_events = LocalPlanEvent.query.filter(
        LocalPlanEvent.timetable == event.timetable,
        LocalPlanEvent.event_category == event.event_category,
        LocalPlanEvent.created_date < event.created_date,
    ).all()
    return True if not earlier_events else False


def _get_save_and_continue_url(plan_reference, event_category):
    match event_category:
        case EventCategory.ESTIMATED_REGULATION_18:
            return url_for(
                "local_plan.add_timetable_event",
                reference=plan_reference,
                event_category=EventCategory.ESTIMATED_REGULATION_19,
            )
        case EventCategory.ESTIMATED_REGULATION_19:
            return url_for(
                "local_plan.add_timetable_event",
                reference=plan_reference,
                event_category=EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION,
            )
        case _:
            return None


def _get_event_form(obj=None, event_category=None):
    return ConsultationForm(obj=obj, event_category=event_category)
