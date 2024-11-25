from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, url_for
from slugify import slugify

from application.blueprints.document.forms import DocumentForm, EditDocumentForm
from application.extensions import db
from application.models import (
    LocalPlan,
    LocalPlanDocument,
    LocalPlanDocumentType,
    Organisation,
    Status,
)
from application.utils import (
    generate_random_string,
    login_required,
    populate_object,
    set_organisations,
)

document = Blueprint(
    "document",
    __name__,
    url_prefix="/local-plan/<string:local_plan_reference>/document",
)


@document.route("/", methods=["GET", "POST"])
@login_required
def add(local_plan_reference):
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        abort(404)

    form = DocumentForm()
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
        (dt.reference, dt.name)
        for dt in LocalPlanDocumentType.query.filter(
            LocalPlanDocumentType.end_date.is_(None)
        )
        .order_by(LocalPlanDocumentType.name)
        .all()
    ]
    if form.validate_on_submit():
        reference = _make_reference(form, plan.reference)
        doc = LocalPlanDocument(
            reference=reference,
            name=form.name.data,
            description=form.description.data,
            documentation_url=form.documentation_url.data,
            document_url=form.document_url.data,
        )
        if form.for_publication.data:
            doc.status = Status.FOR_PLATFORM
        if form.organisations.data:
            set_organisations(doc, form.organisations.data)
        if form.document_types.data:
            doc.document_types = form.document_types.data
        plan.documents.append(doc)
        db.session.add(plan)
        db.session.commit()
        return redirect(
            url_for(
                "document.get_document",
                local_plan_reference=plan.reference,
                reference=doc.reference,
            )
        )

    return render_template("document/add.html", plan=plan, form=form)


@document.route("/<string:reference>")
def get_document(local_plan_reference, reference):
    doc = LocalPlanDocument.query.filter(
        LocalPlanDocument.local_plan == local_plan_reference,
        LocalPlanDocument.reference == reference,
    ).one_or_none()
    if doc is None:
        return abort(404)
    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": "Plans by organisation",
                "href": url_for("organisation.organisations"),
            },
            {
                "text": doc.plan.name,
                "href": url_for("local_plan.get_plan", reference=local_plan_reference),
            },
            {"text": doc.name},
        ]
    }
    return render_template(
        "document/document.html", plan=doc.plan, document=doc, breadcrumbs=breadcrumbs
    )


@document.route("/<string:reference>/edit", methods=["GET", "POST"])
@login_required
def edit(local_plan_reference, reference):
    doc = LocalPlanDocument.query.filter(
        LocalPlanDocument.local_plan == local_plan_reference,
        LocalPlanDocument.reference == reference,
    ).one_or_none()
    if doc is None:
        return abort(404)

    organisation__string = ";".join([org.organisation for org in doc.organisations])

    doc.organisations.clear()
    form = EditDocumentForm(obj=doc, document=doc)

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
    form.document_types.choices = [
        (dt.reference, dt.name)
        for dt in LocalPlanDocumentType.query.filter(
            LocalPlanDocumentType.end_date.is_(None)
        )
        .order_by(LocalPlanDocumentType.name)
        .all()
    ]

    if form.validate_on_submit():
        document = populate_object(form, doc)
        db.session.add(document)
        db.session.commit()
        return redirect(
            url_for(
                "document.get_document",
                local_plan_reference=document.plan.reference,
                reference=document.reference,
            )
        )
    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": "Plans by organisation",
                "href": url_for("organisation.organisations"),
            },
            {
                "text": doc.plan.name,
                "href": url_for("local_plan.get_plan", reference=local_plan_reference),
            },
            {
                "text": doc.name,
                "href": url_for(
                    "document.get_document",
                    local_plan_reference=local_plan_reference,
                    reference=reference,
                ),
            },
            {"text": "Edit"},
        ]
    }
    return render_template(
        "document/edit.html",
        plan=doc.plan,
        document=doc,
        form=form,
        breadcrumbs=breadcrumbs,
    )


def _make_reference(form, plan_reference):
    reference = slugify(form.name.data)
    doc = LocalPlanDocument.query.filter(
        LocalPlanDocument.local_plan == plan_reference,
        LocalPlanDocument.reference == reference,
    ).one_or_none()

    if doc is None:
        return reference

    reference = slugify(f"{reference}-{plan_reference}")
    doc = LocalPlanDocument.query.filter(
        LocalPlanDocument.local_plan == plan_reference,
        LocalPlanDocument.reference == reference,
    ).one_or_none()

    if doc is None:
        return reference

    reference = f"{reference}-{datetime.now().strftime('%Y-%m-%d')}"
    doc = LocalPlanDocument.query.filter(
        LocalPlanDocument.local_plan == plan_reference,
        LocalPlanDocument.reference == reference,
    ).one_or_none()

    if doc is None:
        return reference

    return f"{reference}-{generate_random_string(6)}"
