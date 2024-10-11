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
    LocalPlanDocument,
    Organisation,
    Status,
)
from application.utils import get_centre_and_bounds, login_required, populate_object

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

    form.status.choices = [(s.name, s.value) for s in Status if s != Status.PUBLISHED]

    if form.validate_on_submit():
        reference = slugify(form.name.data)

        # TODO: check if reference already exists and if so append something - maybe the plan period?

        plan = LocalPlan(
            reference=reference,
        )
        populate_object(form, plan)
        # TODO: add boundary - default will be the organisation/organisatios boundary - combined if necessary
        db.session.add(plan)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=plan.reference))

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

    form.status.choices = [(s.name, s.value) for s in Status if s != Status.PUBLISHED]

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


def _get_document_counts(documents):
    counts = {}
    for status in Status:
        counts[status.value] = len([doc for doc in documents if doc.status == status])
    return counts
