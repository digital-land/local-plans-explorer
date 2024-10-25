import base64
import csv
import os
from datetime import datetime
from pathlib import Path

import click
import github
import requests
from flask import current_app
from flask.cli import AppGroup
from slugify import slugify
from sqlalchemy import not_, select, text
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import joinedload

from application.export import (
    LocalPlanBoundaryModel,
    LocalPlanDocumentModel,
    LocalPlanModel,
)
from application.extensions import db
from application.models import (
    LocalPlan,
    LocalPlanBoundary,
    LocalPlanDocument,
    LocalPlanDocumentType,
    LocalPlanEvent,
    LocalPlanEventType,
    LocalPlanTimetable,
    Organisation,
    Status,
    document_organisation,
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
        if org["dataset"] not in [
            "local-authority",
            "development-corporation",
            "national-park-authority",
        ]:
            print(
                "Skipping org",
                org["organisation"],
                "as not a local authority, development corporation or national park authority",
            )
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
        entity = data["entities"][0].get("entity")
        geojson_url = f"https://www.planning.data.gov.uk/entity/{entity}.geojson"
        try:
            resp = requests.get(geojson_url)
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
        doc.organisations = doc.plan.organisations
        db.session.add(doc)
        db.session.commit()


@data_cli.command("export-data")
def export_data():
    updated_data = False
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data", "export")

    if not os.path.exists(data_directory):
        os.makedirs(data_directory)

    local_plan_file_path = os.path.join(data_directory, "local-plan.csv")
    local_plan__document_file_path = os.path.join(
        data_directory, "local-plan-document.csv"
    )

    local_plans = (
        LocalPlan.query.filter(
            LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED])
        )
        .order_by(LocalPlan.reference)
        .all()
    )

    boundaries_to_export = set([])

    if local_plans:
        with open(local_plan_file_path, mode="w") as file:
            fieldnames = list(LocalPlanModel.model_fields.keys())
            fieldnames = [field.replace("_", "-") for field in fieldnames]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for obj in local_plans:
                if obj.boundary_status in [Status.FOR_PLATFORM, Status.EXPORTED]:
                    boundaries_to_export.add(obj.local_plan_boundary)
                m = LocalPlanModel.model_validate(obj)
                data = m.model_dump(by_alias=True)
                writer.writerow(data)
                obj.status = Status.EXPORTED
                db.session.add(obj)
                db.session.commit()
        print(f"{len(local_plans)} local plans exported")
        updated_data = True
    else:
        print("No local plans found for export")

    stmt = (
        select(LocalPlanDocument)
        .join(LocalPlan, LocalPlanDocument.plan)
        .where(
            LocalPlanDocument.status.in_([Status.FOR_PLATFORM, Status.EXPORTED]),
            LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED]),
        )
        .options(joinedload(LocalPlanDocument.plan))
        .order_by(LocalPlanDocument.reference)
    )

    local_plan_documents = db.session.scalars(stmt).unique().all()

    if local_plan_documents:
        with open(local_plan__document_file_path, mode="w") as file:
            fieldnames = list(LocalPlanDocumentModel.model_fields.keys())
            fieldnames = [field.replace("_", "-") for field in fieldnames]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for doc in local_plan_documents:
                m = LocalPlanDocumentModel.model_validate(doc)
                data = m.model_dump(by_alias=True)
                writer.writerow(data)
                doc.status = Status.EXPORTED
                db.session.add(doc)
                db.session.commit()
            print(f"{len(local_plan_documents)} local plan documents exported")
            updated_data = True
    else:
        print("No local plan documents found for export")

    boundaries = LocalPlanBoundary.query.filter(
        LocalPlanBoundary.reference.in_(boundaries_to_export)
    ).all()

    if boundaries:
        boundary_file_path = os.path.join(data_directory, "local-plan-boundary.csv")
        with open(boundary_file_path, mode="w") as file:
            fieldnames = list(LocalPlanBoundaryModel.model_fields.keys())
            fieldnames = [field.replace("_", "-") for field in fieldnames]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for boundary in boundaries:
                m = LocalPlanBoundaryModel.model_validate(boundary)
                data = m.model_dump(by_alias=True)
                writer.writerow(data)
                for local_plan in boundary.local_plans:
                    local_plan.boundary_status = Status.EXPORTED
                    db.session.add(local_plan)
        db.session.commit()
        print(f"{len(boundaries)} local plan boundaries exported")
        updated_data = True

    return updated_data


@data_cli.command("push-export")
def push_export():
    current_file_path = Path(__file__).resolve()
    export_directory = os.path.join(current_file_path.parent.parent, "data", "export")

    repo_data_path = os.getenv("LOCAL_PLANS_REPO_DATA_PATH")
    repo = _get_repo(os.environ)

    print("Pushing changes for", repo, "and path", repo_data_path)

    for csv_file in [
        "local-plan.csv",
        "local-plan-document.csv",
        "local-plan-boundary.csv",
    ]:
        file_path = os.path.join(export_directory, csv_file)
        try:
            with open(file_path, "r") as f:
                local_content = f.read()
        except FileNotFoundError:
            print(f"Local file {file_path} not found. Skipping.")
            continue

        remote_path = os.path.join(repo_data_path, csv_file)
        file, remote_content = _get_file_contents(repo, remote_path)

        if file is None or local_content != remote_content:
            _commit(repo, file, local_content)
        else:
            print(f"No changes in {file_path}. No commit needed.")

    print("Done")


def _get_repo(config):
    app_id = config.get("GITHUB_APP_ID")
    repo_name = config.get("LOCAL_PLANS_REPO_NAME")
    base64_key = config.get("GITHUB_APP_PRIVATE_KEY")
    private_key = base64.b64decode(base64_key)
    private_key_decoded = private_key.decode("utf-8")
    auth = github.Auth.AppAuth(app_id, private_key_decoded)
    gi = github.GithubIntegration(auth=auth)
    installation_id = gi.get_installations()[0].id
    gh = gi.get_github_for_installation(installation_id)
    return gh.get_repo(repo_name)


def _get_file_contents(repo, file_path):
    try:
        file = repo.get_contents(file_path)
        file_content = file.decoded_content.decode("utf-8")
        return file, file_content
    except github.GithubException as e:
        # Handle the case where the file doesn't exist in the repo
        print(f"Error fetching file {file_path}: {e}")
        return None, None


def _commit(repo, file, contents, message="Updated local-plan data"):
    if file is None:
        print(
            f"File not found or error in fetching file. Skipping commit for {file.path}."
        )
        return
    if contents != file.decoded_content.decode("utf-8"):
        repo.update_file(file.path, message, contents, file.sha)
        print(f"{file.path} updated successfully!")
    else:
        print(f"No changes detected in {file.path}. Skipping commit.")


@data_cli.command("export")
@click.pass_context
def export(ctx):
    update_needed = ctx.invoke(export_data)
    if update_needed:
        ctx.invoke(push_export)
        print("Export complete")
    else:
        print("No data to export")


@data_cli.command("default-boundaries")
def set_default_boundaries():
    from application.models import Organisation

    orgs = Organisation.query.filter(Organisation.geometry.isnot(None)).all()
    for org in orgs:
        reference = org.statistical_geography
        boundary = LocalPlanBoundary.query.get(reference)
        if boundary is None:
            boundary = LocalPlanBoundary(
                reference=reference,
                name=f"{org.name} statistical geography",
                description="Default local plan boundary",
                geometry=org.geometry,
                geojson=org.geojson,
                plan_boundary_type="statistical-geography",
            )
            boundary.organisations.append(org)

        for plan in org.local_plans:
            if plan.local_plan_boundary is None:
                plan.local_plan_boundary = boundary.reference
                plan.boundary_status = Status.FOR_REVIEW
                boundary.local_plans.append(plan)
                print("Boundary set for plan", plan.reference)

        db.session.add(boundary)
        db.session.commit()

    print("Default boundaries set")


@data_cli.command("load-doc-types")
def load_doc_types():
    document_types_url = (
        "https://dluhc-datasets.planning-data.dev/dataset/local-plan-document-type.json"
    )
    try:
        resp = requests.get(document_types_url)
        resp.raise_for_status()
        data = resp.json()
        for doc_type in data["records"]:
            name = doc_type["name"]
            reference = doc_type["reference"]
            entry_date = doc_type["entry-date"]
            end_date = doc_type.get("end-date") if doc_type.get("end-date") else None
            sql = text(
                """
                    INSERT INTO local_plan_document_type (name, reference, entry_date, end_date)
                    VALUES (:name, :reference, :entry_date, :end_date)
                    ON CONFLICT (reference)
                    DO UPDATE
                    SET end_date = EXCLUDED.end_date;
                """
            )
            db.session.execute(
                sql,
                {
                    "name": name,
                    "reference": reference,
                    "entry_date": entry_date,
                    "end_date": end_date,
                },
            )
        db.session.commit()
    except requests.exceptions.HTTPError as e:
        print("Error fetching document types:", e)


@data_cli.command("load-event-types")
def load_event_types():
    event_types_url = (
        "https://dluhc-datasets.planning-data.dev/dataset/local-plan-event.json"
    )
    try:
        resp = requests.get(event_types_url)
        resp.raise_for_status()
        data = resp.json()
        for event_type in data["records"]:
            name = event_type["name"]
            reference = event_type["reference"]
            entry_date = event_type["entry-date"]
            end_date = (
                event_type.get("end-date") if event_type.get("end-date") else None
            )
            sql = text(
                """
                    INSERT INTO local_plan_event_type (name, reference, entry_date, end_date)
                    VALUES (:name, :reference, :entry_date, :end_date)
                    ON CONFLICT (reference)
                    DO UPDATE
                    SET end_date = EXCLUDED.end_date;
                """
            )
            db.session.execute(
                sql,
                {
                    "name": name,
                    "reference": reference,
                    "entry_date": entry_date,
                    "end_date": end_date,
                },
            )
        db.session.commit()
    except requests.exceptions.HTTPError as e:
        print("Error fetching event types:", e)


@data_cli.command("load-all")
@click.pass_context
def load_all(ctx):
    ctx.invoke(load_orgs)
    ctx.invoke(load_plans)
    ctx.invoke(load_boundaries)
    ctx.invoke(set_default_boundaries)
    ctx.invoke(load_doc_types)
    ctx.invoke(load_event_types)
    print("Data load complete")


@data_cli.command("load-db-backup")
def load_db_backup():
    import subprocess
    import sys
    import tempfile

    # check heroku cli installed
    result = subprocess.run(["which", "heroku"], capture_output=True, text=True)

    if result.returncode == 1:
        print("Heroku CLI is not installed. Please install it and try again.")
        sys.exit(1)

    # check heroku login
    result = subprocess.run(["heroku", "whoami"], capture_output=True, text=True)

    if "Error: not logged in" in result.stderr:
        print("Please login to heroku using 'heroku login' and try again.")
        sys.exit(1)

    print("Starting load data into", current_app.config["SQLALCHEMY_DATABASE_URI"])
    if (
        input(
            "Completing process will overwrite your local database. Enter 'y' to continue, or anything else to exit. "
        )
        != "y"
    ):
        print("Exiting without making any changes")
        sys.exit(0)

    with tempfile.TemporaryDirectory() as tempdir:
        path = os.path.join(tempdir, "latest.dump")

        # get the latest dump from heroku
        result = subprocess.run(
            [
                "heroku",
                "pg:backups:download",
                "-a",
                "local-plans-explorer",
                "-o",
                path,
            ]
        )

        if result.returncode != 0:
            print("Error downloading the backup")
            sys.exit(1)

        # restore the dump to the local database
        subprocess.run(
            [
                "pg_restore",
                "--verbose",
                "--clean",
                "--no-acl",
                "--no-owner",
                "-h",
                "localhost",
                "-d",
                "local_plans",
                path,
            ]
        )
        print(
            "\n\nRestored the dump to the local database using pg_restore. You can ignore warnings from pg_restore."
        )

    print("Data loaded successfully")


@data_cli.command("set-org-websites")
def set_org_websites():
    base_url = "https://datasette.planning.data.gov.uk/digital-land/organisation.json"
    orgs = Organisation.query.all()
    for org in orgs:
        params = {
            "website__notblank": 1,
            "organisation__exact": org.organisation,
            "_shape": "array",
        }

        try:
            resp = requests.get(base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            print(f"Fetching data for {org.organisation}")
            if len(data) > 0:
                website = data[0].get("website")
                if website:
                    org.website = website
                    db.session.add(org)
                    db.session.commit()
                    print(f"Set website {website} for {org.organisation}")
            else:
                print(f"No website found for {org.organisation}")
        except Exception as e:
            print(f"Error fetching data for {org.organisation}: {e}")
            continue


@data_cli.command("housing-numbers-timetable-data")
def load_housing_numbers_timetable_data():
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data")
    file_path = os.path.join(data_directory, "local-plan-housing-numbers-prototype.csv")

    with open(file_path, mode="r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            documentation_url = row.get("documentation_url")
            if documentation_url.endswith("/"):
                documentation_url = documentation_url[:-1]
            if documentation_url:
                plan = LocalPlan.query.filter(
                    LocalPlan.documentation_url == documentation_url
                ).first()
                if plan is not None and plan.timetable is None:
                    print("Updating plan timetable", plan.reference)
                    plan.period_start_date = (
                        (
                            row.get("period_start_date")
                            if row.get("period_start_date")
                            else None
                        ),
                    )
                    plan.period_end_date = (
                        (
                            row.get("period_end_date")
                            if row.get("period_end_date")
                            else None
                        ),
                    )
                    plan.adopted_date = (
                        row.get("adopted_date") if row.get("adopted_date") else None
                    )
                    db.session.add(plan)
                    dates = [
                        "published_date",
                        "sound_date",
                        "submitted_date",
                        "adopted_date",
                    ]
                    event_types = {
                        "published_date": "reg-19-publication-local-plan-published",
                        "sound_date": "planning‑inspectorate‑found‑sound",
                        "submitted_date": "submit‑plan‑for‑examination",
                        "adopted_date": "plan‑adopted",
                    }

                    events = []
                    for date_field in dates:
                        date_value = row.get(date_field)
                        if date_value:
                            event_type = LocalPlanEventType.query.filter(
                                LocalPlanEventType.reference == event_types[date_field]
                            ).one_or_none()
                            if event_type:
                                event = LocalPlanEvent(
                                    event_type=event_type.reference,
                                    event_date=date_value,
                                )
                                events.append(event)
                    if events:
                        reference = f"{plan.reference}-timetable"
                        timetable = LocalPlanTimetable(
                            reference=reference,
                            events=events,
                            local_plan=plan.reference,
                        )
                        plan.timetable = timetable
                        db.session.add(timetable)
                    db.session.commit()


def _make_reference(name, period_start_date, period_end_date, organisation):
    reference = slugify(name)
    if LocalPlan.query.get(reference) is None:
        return reference

    reference = slugify(f"{organisation.name}-{name}")
    if LocalPlan.query.get(reference) is None:
        return reference

    reference = slugify(f"{reference}-{period_start_date}-{period_end_date}")
    if LocalPlan.query.get(reference) is None:
        return reference

    reference = f"{reference}-{datetime.now().strftime('%Y-%m-%d')}"
    if LocalPlan.query.get(reference) is None:
        return reference

    return reference


@data_cli.command("migrate-doc-types")
def migrate_doc_types():
    documents = LocalPlanDocument.query.filter(
        LocalPlanDocument.document_types.isnot(None)
    ).all()
    for document in documents:
        updated_document_types = []
        for doc_type in document.document_types:
            ref = doc_type.lower().replace("_", "-")
            if ref == "financial-viability-study":
                ref = "viability-assessment"
            document_type = LocalPlanDocumentType.query.get(ref)
            if document_type is None:
                print(
                    f"No matching document type found for {ref} for document {document.reference}"
                )
            else:
                updated_document_types.append(document_type.reference)
        if updated_document_types:
            document.document_types = updated_document_types
            db.session.add(document)
            db.session.commit()
            print(f"Updated document types for {document.reference}")
