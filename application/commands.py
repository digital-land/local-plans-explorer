import csv
import os
from pathlib import Path

import requests
from flask.cli import AppGroup
from sqlalchemy.inspection import inspect

from application.extensions import db
from application.models import LocalPlan, Organisation, local_plan_organisation

data_cli = AppGroup("data")


@data_cli.command("load-orgs")
def load_orgs():
    url = "https://datasette.planning.data.gov.uk/digital-land/organisation.json?_shape=array"
    orgs = []
    columns = set([column.name for column in inspect(Organisation).c])
    while url:
        resp = requests.get(url)
        try:
            url = resp.links.get("next").get("url")
        except AttributeError:
            url = None
        orgs.extend(resp.json())

    for org in orgs:
        if not org["organisation"]:
            print("Skipping invalid org", org["name"])
            continue
        if org["end_date"]:
            print("Skipping end dated org", org["organisation"])
            continue
        try:
            org_obj = Organisation.query.get(org["organisation"])
            if org_obj is None:
                org_obj = Organisation()
                print("Adding new org", org["organisation"])
            else:
                print("Updating org", org["organisation"])
                for key, value in org.items():
                    if key in columns:
                        v = value if value else None
                        setattr(org_obj, key, v)
            db.session.add(org_obj)
            db.session.commit()
        except Exception as e:
            print(e)
            continue


@data_cli.command("load-plans")
def load_plans():
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data")
    file_path = os.path.join(data_directory, "local-plan.csv")

    with open(file_path, mode="r") as file:
        reader = csv.DictReader(file)
        columns = set([column.name for column in inspect(LocalPlan).c])

        for row in reader:
            try:
                plan = LocalPlan.query.get(row["reference"])
                if plan is None:
                    print("Adding new plan", row["reference"])
                    plan = LocalPlan()
                    for key, value in row.items():
                        k = key.lower().replace("-", "_")
                        if k in columns:
                            setattr(plan, k, value if value else None)
                else:
                    print("Updating plan", row["reference"])
                    for key, value in row.items():
                        k = key.lower().replace("-", "_")
                        if k in columns and not k.endswith("date"):
                            setattr(plan, k, value if value else None)
                db.session.add(plan)
                organisations = row.get("organisations")
                for org in organisations.split(";") if organisations else []:
                    organisation = Organisation.query.get(org)
                    if (
                        organisation is not None
                        and organisation not in plan.organisations
                    ):
                        plan.organisations.append(organisation)
                db.session.commit()
            except Exception as e:
                print(f"Error processing row {row['reference']}: {e}")
                db.session.rollback()


@data_cli.command("load-boundaries")
def load_boundaries():
    print("Loading boundaries")
    orgs = Organisation.query.filter(
        Organisation.statistical_geography.isnot(None)
    ).all()
    for org in orgs:
        print(
            f"Loading boundary for {org.organisation} statistical geography {org.statistical_geography}"
        )
        base_url = "https://datasette.planning.data.gov.uk/local-authority-district/entity.json"
        url = f"{base_url}?reference__exact={org.statistical_geography}&_shape=object&_col=geometry"
        resp = requests.get(url)
        try:
            resp.raise_for_status()
            if resp.json():
                data = resp.json()
                geometry = list(data.values())[0]["geometry"]
                if geometry:
                    org.geometry = geometry
                    db.session.add(org)
                    db.session.commit()
        except Exception as e:
            print(f"Failed to load boundary for {org.organisation}")
            print(e)


@data_cli.command("drop-plans")
def drop_plans():
    db.session.query(local_plan_organisation).delete()
    db.session.commit()
    LocalPlan.query.delete()
    db.session.commit()
    print("Local Plans dropped")
