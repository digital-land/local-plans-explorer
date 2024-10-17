import json
from datetime import datetime

import geopandas as gpd
from flask import Blueprint, abort, redirect, render_template, request, url_for
from slugify import slugify

from application.blueprints.document.forms import DocumentForm
from application.blueprints.local_plan.forms import LocalPlanForm
from application.extensions import db
from application.models import (
    CandidateDocument,
    DocumentStatus,
    DocumentType,
    LocalPlan,
    LocalPlanBoundary,
    LocalPlanDocument,
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

    return render_template(
        "local_plan/plan.html",
        plan=plan,
        geography=geography,
        bounding_box=bounding_box,
        document_counts=document_counts,
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


@local_plan.route("/<string:reference>/find-documents")
@login_required
def find_documents(reference):
    from application.scraping import extract_links_from_page

    plan = LocalPlan.query.get(reference)
    if plan is None:
        abort(404)

    document_types = [doc.value for doc in DocumentType.query.all()]
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
                candidate_document = CandidateDocument(**link)
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
        doc.name
        for doc in DocumentType.query.filter(
            DocumentType.value == candidate.document_type
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
        (dt.name, dt.value) for dt in DocumentType.query.all()
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
