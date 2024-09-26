from flask import Blueprint, abort, redirect, render_template, url_for
from slugify import slugify

from application.blueprints.document.forms import DocumentForm
from application.extensions import db
from application.models import LocalPlan, LocalPlanDocument
from application.utils import get_planning_organisations, set_organisations

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


@document.route("/<string:reference>/edit")
def edit(local_plan_reference):
    lp = LocalPlan.query.get(local_plan_reference)
    if lp is None:
        return abort(404)
    return render_template("document/add.html", local_plan=lp)
