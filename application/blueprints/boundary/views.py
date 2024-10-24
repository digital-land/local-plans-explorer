from flask import Blueprint, abort, redirect, render_template, url_for
from geojson import loads
from shapely.geometry import MultiPolygon, shape
from shapely.geometry.polygon import Polygon
from slugify import slugify

from application.blueprints.boundary.forms import BoundaryForm, EditBoundaryForm
from application.extensions import db
from application.models import LocalPlan, LocalPlanBoundary, Organisation, Status
from application.utils import (
    generate_random_string,
    get_centre_and_bounds,
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
    organisations = (
        Organisation.query.filter(Organisation.end_date.is_(None))
        .order_by(Organisation.name)
        .all()
    )
    organisation_choices = [(org.organisation, org.name) for org in organisations]
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

    organisation__string = ";".join(
        [org.organisation for org in lp_boundary.organisations]
    )
    del lp_boundary.organisations
    form = EditBoundaryForm(obj=lp_boundary)
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
        geojson = form.geojson.data
        if geojson is not None:
            form_geojson = loads(geojson)
            existing_geojson = lp_boundary.geojson
            un_changed = _compare_feature_collections(form_geojson, existing_geojson)
            if un_changed:
                print("Update the existing boundary")
                lp_boundary.name = form.name.data
                lp_boundary.description = form.description.data
                lp_boundary.plan_boundary_type = form.plan_boundary_type.data
                if form.organisations.data:
                    set_organisations(lp_boundary, form.organisations.data)
                db.session.add(lp_boundary)
            else:
                print("Create a new boundary")
                reference = slugify(f"{form.name.data}-{generate_random_string()}")
                geometry = _convert_to_wkt(form_geojson)

                lp_boundary = LocalPlanBoundary(
                    reference=reference,
                    name=form.name.data,
                    description=form.description.data,
                    geometry=geometry,
                    geojson=form_geojson,
                    plan_boundary_type=form.plan_boundary_type.data,
                )
                if form.organisations.data:
                    set_organisations(lp_boundary, form.organisations.data)
                lp_boundary.local_plans.append(plan)

            if form.status.data == Status.FOR_PLATFORM.name:
                plan.boundary_status = Status.FOR_PLATFORM
                db.session.add(plan)

            db.session.add(lp_boundary)
            db.session.commit()

        return redirect(url_for("local_plan.get_plan", reference=local_plan_reference))
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

    coords, bounding_box = get_centre_and_bounds(plan.boundary.geojson)
    geography = {
        "name": plan.name,
        "features": plan.boundary.geojson,
        "coords": coords,
        "bounding_box": bounding_box,
        "reference": boundary.reference,
    }

    return render_template(
        "boundary/boundary.html", plan=plan, boundary=boundary, geography=geography
    )


def _sort_feature(feature):
    geom = shape(feature["geometry"]).wkt
    properties = tuple(sorted(feature["properties"].items()))
    return (geom, properties)


def _compare_feature_collections(feature_collection_1, feature_collection_2):
    if (
        feature_collection_1["type"] != "FeatureCollection"
        or feature_collection_2["type"] != "FeatureCollection"
    ):
        return False

    features_1 = sorted(feature_collection_1["features"], key=_sort_feature)
    features_2 = sorted(feature_collection_2["features"], key=_sort_feature)

    if len(features_1) != len(features_2):
        return False

    for f1, f2 in zip(features_1, features_2):
        if not shape(f1["geometry"]).equals(shape(f2["geometry"])):
            return False

    return True


def _convert_to_wkt(feature_collection):
    polygons = []
    for feature in feature_collection["features"]:
        geometry = shape(feature["geometry"])
        if isinstance(geometry, Polygon):
            polygons.append(geometry)
        elif isinstance(geometry, MultiPolygon):
            polygons.extend(geometry.geoms)

    multi_polygon = MultiPolygon(polygons)
    return multi_polygon.wkt
