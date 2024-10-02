import geopandas as gpd
from flask import Blueprint, abort, redirect, render_template, url_for
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from slugify import slugify

from application.blueprints.local_plan.forms import LocalPlanForm
from application.extensions import db
from application.models import LocalPlan, Status
from application.utils import (
    get_planning_organisations,
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

    # temporary geography hack until we get some boundaries
    feature_collection = {"type": "FeatureCollection", "features": []}
    references = []
    for org in plan.organisations:
        if org.geojson:
            feature_collection["features"].extend(org.geojson["features"])
            references.append(org.geojson["features"][0]["properties"]["reference"])

    if len(feature_collection["features"]) > 0:
        coords, bounding_box = _get_centre_and_bounds(feature_collection)
        geography = {
            "name": plan.name,
            "features": feature_collection,
            "coords": coords,
            "bounding_box": bounding_box,
            "references": ":".join(references),
        }
    else:
        geography = None
        bounding_box = None

    return render_template(
        "local_plan/plan.html",
        plan=plan,
        geography=geography,
        bounding_box=bounding_box,
    )


@local_plan.route("/add", methods=["GET", "POST"])
@login_required
def add():
    form = LocalPlanForm()
    organisation_choices = [
        (org.organisation, org.name) for org in get_planning_organisations()
    ]
    form.organisations.choices = [(" ", " ")] + organisation_choices
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

    return render_template("local_plan/add.html", form=form)


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

    organisation_choices = [
        (org.organisation, org.name) for org in get_planning_organisations()
    ]
    form.organisations.choices = organisation_choices

    form.status.choices = [(s.name, s.value) for s in Status if s != Status.PUBLISHED]

    if form.validate_on_submit():
        plan = populate_object(form, plan)
        db.session.add(plan)
        db.session.commit()
        return redirect(url_for("local_plan.get_plan", reference=plan.reference))

    return render_template("local_plan/edit.html", plan=plan, form=form)


def _get_centre_and_bounds(features):
    if features is not None:
        gdf = gpd.GeoDataFrame.from_features(features)
        bounding_box = list(gdf.total_bounds)
        return {"lat": gdf.centroid.y[0], "long": gdf.centroid.x[0]}, bounding_box
    return None, None


def _combine_geojson_features(features):
    geometries = []
    for feature in features:
        geom = shape(feature["geometry"])
        geometries.append(geom)

    combined_geometry = unary_union(geometries)

    combined_feature = {
        "geometry": mapping(combined_geometry),
    }

    return combined_feature
