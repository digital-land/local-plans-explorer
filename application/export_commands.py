import base64
import csv
import os
from pathlib import Path

import click
import github
from flask.cli import AppGroup
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from application.export import (
    LocalPlanBoundaryModel,
    LocalPlanDocumentModel,
    LocalPlanModel,
    LocalPlanTimetableModel,
)
from application.extensions import db
from application.models import (
    LocalPlan,
    LocalPlanBoundary,
    LocalPlanDocument,
    LocalPlanTimetable,
    Status,
)

export_cli = AppGroup("export")


@export_cli.command("create")
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


@export_cli.command("push")
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


@export_cli.command("all")
@click.pass_context
def export_all(ctx):
    update_needed = ctx.invoke(export_data)
    if update_needed:
        ctx.invoke(push_export)
        print("Export complete")
    else:
        print("No data to export")


@export_cli.command("timetable")
def export_timetable():
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data", "export")

    if not os.path.exists(data_directory):
        os.makedirs(data_directory)

    timetable_file_path = os.path.join(data_directory, "local-plan-timetable.csv")

    timetables = (
        LocalPlanTimetable.query.join(LocalPlanTimetable.local_plan_obj)
        .filter(LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED]))
        .all()
    )
    events = []
    for timetable in timetables:
        for event in timetable.events:
            data = {}
            for index, (key, value) in enumerate(event.event_data.items()):
                event_date = event.collect_iso_date_fields(key)
                if not event_date:
                    continue
                kebabbed_key = key.replace("_", "-")
                ref = f"{event.reference}-{kebabbed_key}"
                data["reference"] = f"{ref}-{index}"
                data["event-date"] = event_date
                data["local-plan"] = timetable.local_plan
                data["notes"] = value.get("notes")
                data["description"] = event.description or ""
                data["event-type"] = kebabbed_key
                data["entry-date"] = event.entry_date
                data["start-date"] = event.start_date
                data["end-date"] = event.end_date
            model = LocalPlanTimetableModel.model_validate(data)
            events.append(model.model_dump(by_alias=True))

    with open(timetable_file_path, mode="w") as file:
        fieldnames = list(LocalPlanTimetableModel.model_fields.keys())
        fieldnames = [field.replace("_", "-") for field in fieldnames]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow(event)
    print(f"{len(events)} local plan timetables exported")


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
