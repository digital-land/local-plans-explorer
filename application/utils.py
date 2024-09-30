from functools import wraps

from sqlalchemy import Date, cast, null, or_

from application.models import LocalPlan, Organisation


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import current_app, redirect, request, session, url_for

        if current_app.config.get("AUTHENTICATION_ON", True):
            if session.get("user") is None:
                return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def get_planning_organisations():
    orgs = (
        Organisation.query.filter(
            or_(
                Organisation.organisation.contains("local-authority"),
                Organisation.organisation.contains("national-park"),
                Organisation.organisation.contains("development-corporation"),
            )
        )
        .filter(
            or_(
                Organisation.end_date.is_(None),
                cast(Organisation.end_date, Date) == null(),
            )
        )
        .order_by(Organisation.name.asc())
        .all()
    )
    return orgs


def get_adopted_plans(with_org_list=True):
    adopted_plans = LocalPlan.query.filter(LocalPlan.adopted_date.isnot(None)).all()
    orgs_with_adopted_plan = [
        organisation for plan in adopted_plans for organisation in plan.organisations
    ]
    if with_org_list:
        return adopted_plans, orgs_with_adopted_plan
    return adopted_plans


def combine_feature_collections(feature_collections):
    combined_features = []

    for fc in feature_collections:
        combined_features.extend(fc["features"])

    combined_fc = {"type": "FeatureCollection", "features": combined_features}

    return combined_fc


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

        obj.adopted_date = f"{form.adopted_date_year.data}-{form.adopted_date_month.data}-{form.adopted_date_day.data}"

        del form.adopted_date_year
        del form.adopted_date_month
        del form.adopted_date_day

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
