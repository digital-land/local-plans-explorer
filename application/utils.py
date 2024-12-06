from functools import wraps

import geopandas as gpd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from application.models import LocalPlan, Organisation, Status


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import current_app, redirect, request, session, url_for

        if current_app.config.get("AUTHENTICATION_ON", True):
            if session.get("user") is None:
                return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def get_plans_for_review():
    return LocalPlan.query.filter(LocalPlan.status == Status.FOR_REVIEW).all()


def get_plans_with_documents_for_review():
    return LocalPlan.query.filter(LocalPlan.status == Status.FOR_REVIEW).all()


def combine_geographies(geographies):
    combined_features = []

    for geojson in geographies:
        if geojson["type"] == "FeatureCollection":
            combined_features.extend(geojson["features"])
        elif geojson["type"] == "Feature":
            combined_features.append(geojson)
        else:
            raise ValueError(f"Unsupported GeoJSON type: {geojson['type']}")

    combined_geographies = {"type": "FeatureCollection", "features": combined_features}

    return combined_geographies


def adopted_plan_count():
    return LocalPlan.query.filter(LocalPlan.adopted_date.isnot(None)).count()


def get_adopted_local_plans():
    return (
        LocalPlan.query.filter(LocalPlan.development_plan_type == "local-plan")
        .filter(LocalPlan.adopted_date.isnot(None))
        .all()
    )


def set_organisations(obj, org_str):
    previous_orgs = [organisation.organisation for organisation in obj.organisations]
    orgs = org_str.split(";")
    # add any new organisations
    for oid in orgs:
        org = Organisation.query.get(oid)
        obj.organisations.append(org)
        if oid in previous_orgs:
            previous_orgs.remove(oid)
    # remove old organisations
    for oid in previous_orgs:
        org = Organisation.query.get(oid)
        obj.organisations.remove(org)


def populate_object(form, obj):
    organisations = form.organisations.data
    del form.organisations
    if isinstance(obj, LocalPlan):
        period_start = form.period_start_date.data
        period_end = form.period_end_date.data

        if period_start:
            obj.period_start_date = int(period_start)
        else:
            obj.period_start_date = None

        if period_end:
            obj.period_end_date = int(period_end)
        else:
            obj.period_end_date = None

        del form.period_start_date
        del form.period_end_date

        if hasattr(form, "status") and form.status.data:
            obj.status = string_to_status(form.status.data)
            del form.status

    form.populate_obj(obj)

    previous_orgs = [organisation.organisation for organisation in obj.organisations]

    if isinstance(organisations, str):
        orgs = organisations.split(";")
        # add any new organisations
        for oid in orgs:
            org = Organisation.query.get(oid)
            obj.organisations.append(org)
            if oid in previous_orgs:
                previous_orgs.remove(oid)
        # remove old organisations
        for oid in previous_orgs:
            org = Organisation.query.get(oid)
            obj.organisations.remove(org)

    elif isinstance(organisations, list):
        for org in organisations:
            organisation = Organisation.query.get(org)
            obj.organisations.append(organisation)

    return obj


def plan_count():
    return LocalPlan.query.count()


def get_plans_query(condition, count=False):
    query = LocalPlan.query.filter(condition)
    if count:
        return query.count()
    return query.all()


def get_centre_and_bounds(features):
    if features is not None:
        gdf = gpd.GeoDataFrame.from_features(features)
        bounding_box = list(gdf.total_bounds)
        return {"lat": gdf.centroid.y[0], "long": gdf.centroid.x[0]}, bounding_box
    return None, None


def combine_geojson_features(features):
    geometries = []
    for feature in features:
        geom = shape(feature["geometry"])
        geometries.append(geom)

    combined_geometry = unary_union(geometries)

    combined_feature = {
        "geometry": mapping(combined_geometry),
    }

    return combined_feature


def generate_random_string(length=6):
    import random
    import string

    characters = (
        string.ascii_lowercase + string.digits
    )  # Contains both letters and digits
    random_string = "".join(random.choice(characters) for _ in range(length))
    return random_string


def string_to_status(status_string):
    try:
        enum_parts = status_string.split(".")
        if len(enum_parts) == 1:
            enum_name = enum_parts[0]
        else:
            enum_name = enum_parts[1]
        return Status[enum_name]
    except (IndexError, KeyError):
        print(f"Invalid status string: {status_string}")
        return Status.FOR_REVIEW
