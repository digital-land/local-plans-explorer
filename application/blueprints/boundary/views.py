from flask import Blueprint, abort, redirect, render_template, url_for
from slugify import slugify

from application.blueprints.boundary.forms import BoundaryForm
from application.extensions import db
from application.models import LocalPlan, LocalPlanBoundary
from application.utils import (
    get_planning_organisations,
    login_required,
    set_organisations,
)

boundary = Blueprint(
    "boundary",
    __name__,
    url_prefix="/local-plan/<string:local_plan_reference>/boundary",
)


@boundary.route("/", methods=["GET", "POST"])
@login_required
def add(local_plan_reference):
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        abort(404)

    form = BoundaryForm()
    organisation_choices = [
        (org.organisation, org.name) for org in get_planning_organisations()
    ]
    form.organisations.choices = [(" ", " ")] + organisation_choices
    organisation__string = ";".join([org.organisation for org in plan.organisations])
    form.organisations.data = organisation__string

    if form.validate_on_submit():
        reference = slugify(form.name.data)
        boundary = LocalPlanBoundary.query.get(reference)
        if boundary is not None:
            form.name.errors.append("Boundary with this name already exists")
            return render_template("boundary/add.html", plan=plan, form=form)

        boundary = LocalPlanBoundary(
            reference=reference,
            name=form.name.data,
            description=form.description.data,
            geometry=form.geometry.data,
            plan_boundary_type=form.plan_boundary_type.data,
        )
        if form.organisations.data:
            set_organisations(boundary, form.organisations.data)

        boundary.local_plans.append(plan)
        db.session.add(boundary)
        db.session.commit()

        return redirect(
            url_for(
                "boundary.get_boundary",
                local_plan_reference=local_plan_reference,
                reference="some-reference",
            )
        )

    return render_template("boundary/add.html", plan=plan, form=form)


@boundary.route("/<string:reference>/edit", methods=["GET", "POST"])
@login_required
def edit(local_plan_reference, reference):
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        return abort(404)
    lp_boundary = LocalPlanBoundary.query.get(reference)
    if lp_boundary is None:
        return abort(404)

    form = BoundaryForm()
    organisation_choices = [
        (org.organisation, org.name) for org in get_planning_organisations()
    ]
    form.organisations.choices = [(" ", " ")] + organisation_choices
    organisation__string = ";".join([org.organisation for org in plan.organisations])
    form.organisations.data = organisation__string

    if form.validate_on_submit():
        return redirect(
            url_for(
                "boundary.get_boundary",
                local_plan_reference=local_plan_reference,
                boundary_reference="some-reference",
            )
        )
    return render_template(
        "boundary/edit.html", plan=plan, form=form, boundary=lp_boundary
    )


@boundary.route("/<string:reference>")
def get_boundary(local_plan_reference, reference):
    plan = LocalPlan.query.get(local_plan_reference)
    if plan is None:
        abort(404)
    boundary = LocalPlanBoundary.query.get(reference)
    if boundary is None:
        return abort(404)
    return render_template("boundary/boundary.html", plan=plan, boundary=boundary)
