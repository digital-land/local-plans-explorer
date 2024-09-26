from flask import Blueprint, abort, redirect, render_template, url_for
from slugify import slugify

from application.blueprints.document.forms import DocumentForm
from application.extensions import db
from application.models import LocalPlan, LocalPlanDocument, Status
from application.utils import (
    get_planning_organisations,
    populate_object,
    set_organisations,
)

document = Blueprint(
    "document",
    __name__,
    url_prefix="/local-plan/<string:local_plan_reference>/document",
)


@document.route("/", methods=["GET", "POST"])
def add(local_plan_reference):
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        abort(404)

    form = DocumentForm()
    organisation_choices = [
        (org.organisation, org.name) for org in get_planning_organisations()
    ]
    form.organisations.choices = [(" ", " ")] + organisation_choices

    if form.validate_on_submit():
        reference = slugify(form.name.data)
        doc = LocalPlanDocument(
            reference=reference,
            name=form.name.data,
            description=form.description.data,
            documentation_url=form.documentation_url.data,
            document_url=form.document_url.data,
        )
        set_organisations(doc, form.organisations.data)
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
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        abort(404)
    doc = LocalPlanDocument.query.get(reference)
    if doc is None:
        return abort(404)
    return render_template("document/document.html", plan=plan, local_plan_document=doc)


@document.route("/<string:reference>/edit", methods=["GET", "POST"])
def edit(local_plan_reference, reference):
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        return abort(404)
    doc = LocalPlanDocument.query.get(reference)
    if doc is None:
        return abort(404)

    organisation__string = ";".join([org.organisation for org in doc.organisations])

    del doc.organisations
    form = DocumentForm(obj=doc)

    if not form.organisations.data:
        form.organisations.data = organisation__string

    organisation_choices = [
        (org.organisation, org.name) for org in get_planning_organisations()
    ]

    form.organisations.choices = organisation_choices
    form.status.choices = [(s.name, s.value) for s in Status if s != Status.PUBLISHED]

    if form.validate_on_submit():
        document = populate_object(form, doc)
        db.session.add(document)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=plan.reference))

    return render_template("document/edit.html", plan=plan, document=doc, form=form)
