import geopandas as gpd
import slugify
from flask import Blueprint, abort, redirect, render_template, url_for

from application.blueprints.local_plan.forms import LocalPlanForm
from application.extensions import db
from application.models import LocalPlan, Status
from application.utils import get_planning_organisations, populate_object

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
    geographies = []
    # temporary geography hack until we get some boundaries
    features = []
    for org in plan.organisations:
        if org.geometry:
            coords, _ = _get_centre_and_bounds(org.geojson["features"])
            geographies.append(
                {
                    "geojson": org.geojson,
                    "coords": coords,
                    "reference": org.statistical_geography,
                }
            )
            features.extend(org.geojson["features"])

    if features:
        _, bounding_box = _get_centre_and_bounds(features)
    else:
        bounding_box = None

    return render_template(
        "local_plan/plan.html",
        plan=plan,
        geographies=geographies,
        bounding_box=bounding_box,
    )


@local_plan.route("/add")
def add():
    form = LocalPlanForm()
    organisation_choices = [
        (org.organisation, org.name) for org in get_planning_organisations()
    ]
    form.organisations.choices = [(" ", " ")] + organisation_choices

    if form.validate_on_submit():
        reference = slugify(form.name.data)
        plan = LocalPlan(
            reference=reference,
            name=form.name.data,
            description=form.description.data,
            period_start_date=form.date_created.data,
            period_end_date=form.date_updated.data,
        )
        db.session.add(plan)
        db.session.commit()
        return redirect(url_for("local_plan.get_local_plan", reference=plan.reference))

    return render_template("local_plan/add.html", form=form)


@local_plan.route("/<string:reference>/edit", methods=["GET", "POST"])
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
