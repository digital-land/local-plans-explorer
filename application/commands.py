import csv
import os
from pathlib import Path

import requests
from flask.cli import AppGroup
from sqlalchemy.inspection import inspect

from application.extensions import db
from application.models import (
    DocumentType,
    LocalPlan,
    LocalPlanDocument,
    Organisation,
    local_plan_organisation,
)

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
    from application.extensions import db

    orgs = Organisation.query.all()
    for org in orgs:
        curie = f"statistical-geography:{org.statistical_geography}"
        g = _get_geography(curie)
        if g is not None:
            print("Loading boundary for", org.organisation)
            org.geometry = g["geometry"]
            org.geojson = g["geojson"]
            org.point = g["point"]
            db.session.add(org)
            db.session.commit()
        else:
            print("No boundary found for", org.organisation)


def _get_geography(reference):
    url = "https://www.planning.data.gov.uk/entity.json"
    params = {"curie": reference}
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status
        data = resp.json()
        if len(data["entities"]) == 0:
            print("No entities found for url", resp.url)
            return None
        point = data["entities"][0].get("point")
        geojson_url = "https://www.planning.data.gov.uk/entity.geojson"
        try:
            resp = requests.get(geojson_url, params=params)
            resp.raise_for_status()
            geography = {
                "geojson": resp.json(),
                "geometry": data["entities"][0].get("geometry"),
                "point": point,
            }
            return geography
        except Exception as e:
            print(e)
            return None
    except Exception as e:
        print(e)
        return None


@data_cli.command("drop-plans")
def drop_plans():
    db.session.query(local_plan_organisation).delete()
    db.session.commit()
    LocalPlan.query.delete()
    db.session.commit()
    print("Local Plans dropped")


@data_cli.command("load-docs")
def load_docs():
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data")
    file_path = os.path.join(data_directory, "local-plan-documents.csv")

    document_types = None

    with open(file_path, mode="r") as file:
        reader = csv.DictReader(file)
        columns = set([column.name for column in inspect(LocalPlanDocument).c])

        for row in reader:
            try:
                plan = LocalPlan.query.get(row["local-plan"])
                if plan is None:
                    print(
                        "Skipping document", row["reference"], "as local plan not found"
                    )
                    continue
                document = LocalPlanDocument.query.filter(
                    LocalPlanDocument.local_plan == plan.reference,
                    LocalPlanDocument.reference == row["reference"],
                ).one_or_none()

                document_type = row.pop("document-types", None)
                if document_type is not None:
                    document_type = document_type.replace("-", "_").upper()

                if document_type is not None:
                    doc_type = DocumentType.query.get(document_type)
                    if doc_type is None:
                        value = document_type.replace("_", " ")
                        value = value[0].upper() + value[1:].lower()
                        doc_type = DocumentType(name=document_type, value=value)
                        db.session.add(doc_type)

                document_types = [document_type] if document_type else []

                if document is None:
                    print("Adding new local plan document", row["reference"])
                    document = LocalPlanDocument()
                    for key, value in row.items():
                        k = key.lower().replace("-", "_")
                        if k in columns:
                            setattr(document, k, value if value else None)

                    document.document_types = document_types
                    organisations = row.get("organisations")
                    if organisations:
                        for org in organisations.split(";") if organisations else []:
                            organisation = Organisation.query.get(org)
                            if (
                                organisation is not None
                                and organisation not in document.organisations
                            ):
                                document.organisations.append(organisation)
                                db.session.add(organisation)
                    else:
                        for org in plan.organisations:
                            if org not in document.organisations:
                                document.organisations.append(org)
                                db.session.add(org)
                    if document not in plan.documents:
                        plan.documents.append(document)
                    db.session.add(plan)
                    db.session.add(document)
                    db.session.commit()

                else:
                    print("local plan document", row["reference"], "already loaded")

                    # for key, value in row.items():
                    #     k = key.lower().replace("-", "_")
                    #     if k in columns and not k.endswith("date"):
                    #         setattr(document, k, value if value else None)
            except Exception as e:
                print(f"Error processing row {row['reference']}: {e}")
                db.session.rollback()
