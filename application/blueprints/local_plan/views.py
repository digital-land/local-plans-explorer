from flask import Blueprint, abort, redirect, render_template, request, url_for
from slugify import slugify

from application.blueprints.local_plan.forms import LocalPlanForm
from application.extensions import db
from application.models import (
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


@local_plan.route("/<string:reference>/find-documents", methods=["GET", "POST"])
@login_required
def find_documents(reference):
    from application.scraping import extract_links_from_page

    plan = LocalPlan.query.get(reference)
    if plan is None:
        abort(404)

    document_types = [doc.value for doc in DocumentType.query.all()]
    document_links = extract_links_from_page(
        plan.documentation_url, plan.reference, document_types
    )

    for link in document_links:
        document_url = link["document_url"]
        existing_doc = LocalPlanDocument.query.filter(
            LocalPlanDocument.document_url == document_url
        ).one_or_none()
        if existing_doc:
            link["existing"] = existing_doc.reference
            if existing_doc.local_plan == plan.reference:
                link["linked_to_plan"] = True
            else:
                link["linked_to_plan"] = False
        else:
            link["existing"] = None

    return render_template(
        "local_plan/documents-found.html", plan=plan, document_links=document_links
    )


def _get_document_counts(documents):
    counts = {}
    for status in Status:
        counts[status.value] = len([doc for doc in documents if doc.status == status])
    return counts
