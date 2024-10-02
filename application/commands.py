import csv
import os
from pathlib import Path

import requests
from flask.cli import AppGroup
from sqlalchemy import not_, select
from sqlalchemy.inspection import inspect

from application.export import LocalPlanModel
from application.extensions import db
from application.models import (
    LocalPlan,
    LocalPlanDocument,
    Organisation,
    Status,
    document_organisation,
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


@data_cli.command("create-import-docs")
def create_importable_docs():
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data")
    file_path = os.path.join(data_directory, "local-plan-document.csv")
    out_file_path = os.path.join(data_directory, "local-plan-document-copyable.csv")
    with open(file_path, mode="r") as file:
        reader = csv.DictReader(file)
        with open(out_file_path, mode="w") as out_file:
            fieldnames = list(reader.fieldnames) + [
                "start-date",
                "end-date",
                "description",
                "status",
            ]
            fieldnames = [field.replace("-", "_") for field in fieldnames]
            writer = csv.DictWriter(out_file, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                fixed_row = {}
                try:
                    plan = LocalPlan.query.get(row["local-plan"])
                    if plan is None:
                        print(
                            "Skipping document",
                            row["reference"],
                            "as local plan not found",
                        )
                        continue

                    fixed_row["name"] = row["name"]
                    fixed_row["reference"] = row["reference"]
                    fixed_row["local_plan"] = row["local-plan"]
                    fixed_row["document_types"] = (
                        "{" + row["document-types"].replace("-", "_").upper() + "}"
                    )
                    fixed_row["document_url"] = row["document-url"]
                    fixed_row["documentation_url"] = row["documentation-url"]
                    fixed_row["start_date"] = ""
                    fixed_row["description"] = ""
                    fixed_row["status"] = "FOR_REVIEW"
                    writer.writerow(fixed_row)
                except Exception as e:
                    print(f"Error processing row {row['reference']}: {e}")
    print("Copyable file created")


@data_cli.command("export")
def export_data():
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data", "export")

    if not os.path.exists(data_directory):
        os.makedirs(data_directory)

    local_plan_file_path = os.path.join(data_directory, "local-plan.csv")
    local_plan__document_file_path = os.path.join(data_directory, "local-plan.csv")

    local_plans = LocalPlan.query.filter(
        LocalPlan.status == Status.FOR_PUBLICATION
    ).all()

    if local_plans:
        with open(local_plan_file_path, mode="w") as file:
            fieldnames = list(LocalPlanModel.model_fields.keys())
            fieldnames = [field.replace("_", "-") for field in fieldnames]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for obj in local_plans:
                m = LocalPlanModel.model_validate(obj)
                data = m.model_dump(by_alias=True)
                writer.writerow(data)
                obj.status = Status.PUBLISHED
                db.session.add(obj)
                db.session.commit()
        print(f"{len(local_plans)} local plans exported")
    else:
        print("No local plans found for export")

    local_plan_documents = LocalPlanModel.query.filter(
        LocalPlan.status == Status.FOR_PUBLICATION
    ).all()

    if local_plan_documents:
        with open(local_plan__document_file_path, mode="w") as file:
            fieldnames = list(LocalPlanModel.model_fields.keys())
            fieldnames = [field.replace("_", "-") for field in fieldnames]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for plan in local_plans:
                for doc in plan.documents:
                    m = LocalPlanModel.model_validate(doc)
                    data = m.model_dump(by_alias=True)
                    writer.writerow(data)
                    doc.status = Status.PUBLISHED
                    db.session.add(doc)
                    db.session.commit()
            print(f"{len(local_plan_documents)} local plan documents exported")
    else:
        print("No local plan documents found for export")


@data_cli.command("set-orgs")
def set_orgs():
    subquery = (
        select(document_organisation.c.local_plan_document_reference)
        .where(
            document_organisation.c.local_plan_document_reference
            == LocalPlanDocument.reference
        )
        .exists()
    )
    query = select(LocalPlanDocument).where(not_(subquery))
    result = db.session.execute(query).scalars().all()

    for doc in result:
        doc.organisations = doc.local_plan_obj.organisations
        db.session.add(doc)
        db.session.commit()
