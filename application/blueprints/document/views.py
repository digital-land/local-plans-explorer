from flask import Blueprint, abort, redirect, render_template, url_for
from slugify import slugify

from application.blueprints.document.forms import DocumentForm, EditDocumentForm
from application.extensions import db
from application.models import (
    DocumentType,
    LocalPlan,
    LocalPlanDocument,
    Organisation,
    Status,
)
from application.utils import login_required, populate_object, set_organisations

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
        (dt.name, dt.value) for dt in DocumentType.query.all()
    ]
    if form.validate_on_submit():
        reference = slugify(form.name.data)

        doc = LocalPlanDocument.query.filter(
            LocalPlanDocument.local_plan == local_plan_reference,
            LocalPlanDocument.reference == reference,
        ).one_or_none()

        if doc is not None:
            form.name.errors.append("Document with this name already exists")
            return render_template("document/add.html", plan=plan, form=form)

        doc = LocalPlanDocument(
            reference=reference,
            name=form.name.data,
            description=form.description.data,
            documentation_url=form.documentation_url.data,
            document_url=form.document_url.data,
        )
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
    return render_template("document/document.html", plan=doc.plan, document=doc)


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

    del doc.organisations
    form = EditDocumentForm(obj=doc)

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
    form.document_types.choices = [
        (dt.name, dt.value) for dt in DocumentType.query.all()
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

    return render_template("document/edit.html", plan=doc.plan, document=doc, form=form)
