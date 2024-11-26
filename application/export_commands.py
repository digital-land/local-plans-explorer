import base64
import csv
import os
from pathlib import Path

import click
import github
from flask.cli import AppGroup
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func

from application.export import (
    LocalPlanBoundaryModel,
    LocalPlanDocumentModel,
    LocalPlanModel,
    LocalPlanTimetableModel,
)
from application.extensions import db
from application.models import (
    EventCategory,
    LocalPlan,
    LocalPlanBoundary,
    LocalPlanDocument,
    LocalPlanEvent,
    LocalPlanTimetable,
    Status,
)

export_cli = AppGroup("export")


@export_cli.command("create")
def export_data():
    updated_data = False
    current_file_path = Path(__file__).resolve()
    data_directory = os.path.join(current_file_path.parent.parent, "data", "export")
    BATCH_SIZE = 100

    if not os.path.exists(data_directory):
        os.makedirs(data_directory)

    local_plan_file_path = os.path.join(data_directory, "local-plan.csv")
    local_plan__document_file_path = os.path.join(
        data_directory, "local-plan-document.csv"
    )

    # Process local plans in batches
    query = LocalPlan.query.filter(
        LocalPlan.status.in_([Status.FOR_PLATFORM, Status.EXPORTED])
    ).order_by(LocalPlan.reference)

    total_plans = query.count()
    print(f"{total_plans} local plans found for export")

    if total_plans > 0:
        boundaries_to_export = set()
        with open(local_plan_file_path, mode="w") as file:
            fieldnames = [
                field.replace("_", "-") for field in LocalPlanModel.model_fields.keys()
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for offset in range(0, total_plans, BATCH_SIZE):
                plans_batch = query.limit(BATCH_SIZE).offset(offset).all()
                for obj in plans_batch:
                    if obj.boundary_status in [Status.FOR_PLATFORM, Status.EXPORTED]:
                        boundaries_to_export.add(obj.local_plan_boundary)
                    m = LocalPlanModel.model_validate(obj)
                    writer.writerow(m.model_dump(by_alias=True))
                    obj.status = Status.EXPORTED
                    db.session.add(obj)

                db.session.commit()
                db.session.expire_all()  # Clear session

        print(f"{total_plans} local plans exported")
        updated_data = True
    else:
        print("No local plans found for export")

    # Process documents in batches
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

    total_docs = db.session.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar()

    if total_docs > 0:
        with open(local_plan__document_file_path, mode="w") as file:
            fieldnames = [
                field.replace("_", "-")
                for field in LocalPlanDocumentModel.model_fields.keys()
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for offset in range(0, total_docs, BATCH_SIZE):
                docs_batch = (
                    db.session.scalars(stmt.limit(BATCH_SIZE).offset(offset))
                    .unique()
                    .all()
                )
                for doc in docs_batch:
                    m = LocalPlanDocumentModel.model_validate(doc)
                    writer.writerow(m.model_dump(by_alias=True))
                    doc.status = Status.EXPORTED
                    db.session.add(doc)

                db.session.commit()
                db.session.expire_all()

            print(f"{total_docs} local plan documents exported")
            updated_data = True
    else:
        print("No local plan documents found for export")

    # Process boundaries in batches
    if boundaries_to_export:
        boundary_file_path = os.path.join(data_directory, "local-plan-boundary.csv")
        total_boundaries = LocalPlanBoundary.query.filter(
            LocalPlanBoundary.reference.in_(boundaries_to_export)
        ).count()

        if total_boundaries > 0:
            with open(boundary_file_path, mode="w") as file:
                fieldnames = [
                    field.replace("_", "-")
                    for field in LocalPlanBoundaryModel.model_fields.keys()
                ]
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()

                for offset in range(0, total_boundaries, BATCH_SIZE):
                    boundaries_batch = (
                        LocalPlanBoundary.query.filter(
                            LocalPlanBoundary.reference.in_(boundaries_to_export)
                        )
                        .limit(BATCH_SIZE)
                        .offset(offset)
                        .all()
                    )

                    for boundary in boundaries_batch:
                        m = LocalPlanBoundaryModel.model_validate(boundary)
                        writer.writerow(m.model_dump(by_alias=True))
                        for local_plan in boundary.local_plans:
                            local_plan.boundary_status = Status.EXPORTED
                            db.session.add(local_plan)

                    db.session.commit()
                    db.session.expire_all()

                print(f"{total_boundaries} local plan boundaries exported")
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
        # Add LDS published date as first event if it exists
        if timetable.local_plan_obj.lds_published_date:
            lds_published_data = {
                "reference": f"{timetable.reference}-timetable-published",
                "event-date": timetable.local_plan_obj.lds_published_date,
                "local-plan": timetable.local_plan,
                "notes": "Local development scheme published",
                "description": "Local development scheme published",
                "event-type": "timetable-published",
                "entry-date": timetable.entry_date,
                "start-date": timetable.start_date,
                "end-date": timetable.end_date,
            }
            model = LocalPlanTimetableModel.model_validate(lds_published_data)
            events.append(model.model_dump(by_alias=True))

        # Continue with existing event processing
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

        # Add adopted date after processing all events for this timetable
        if timetable.local_plan_obj.adopted_date:
            adopted_date_data = {
                "reference": f"{timetable.reference}-plan-adopted",
                "event-date": timetable.local_plan_obj.adopted_date,
                "local-plan": timetable.local_plan,
                "notes": None,
                "description": "Plan adopted",
                "event-type": "plan-adopted",
                "entry-date": timetable.entry_date,
                "start-date": timetable.start_date,
                "end-date": timetable.end_date,
            }
            model = LocalPlanTimetableModel.model_validate(adopted_date_data)
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


@export_cli.command("migrate-adopted-date")
def migrate_adopted_date():
    events = LocalPlanEvent.query.filter(
        LocalPlanEvent.event_category == EventCategory.PLANNING_INSPECTORATE_FINDINGS
    ).all()

    migrated_count = 0
    for event in events:
        # Get the adoption date from event data
        adopted_date = event.collect_iso_date_fields("plan_adopted")
        if adopted_date:
            # Get the associated local plan and update its adopted date
            local_plan = event.timetable.local_plan_obj
            local_plan.adopted_date = adopted_date

            # Remove the plan_adopted data from the event
            event.event_data.pop("plan_adopted", None)

            # Save both the local plan and the modified event
            db.session.add(local_plan)
            db.session.add(event)

            migrated_count += 1

    if migrated_count > 0:
        db.session.commit()
        print(f"Migrated {migrated_count} adoption dates to local plans")
    else:
        print("No adoption dates found to migrate")
