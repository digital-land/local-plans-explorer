from sqlalchemy import Date, cast, null, or_

from application.models import LocalPlan, Organisation


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
