import pytest
from slugify import slugify

from application.extensions import db
from application.factory import create_app
from application.models import LocalPlan, Organisation


@pytest.fixture(scope="session")
def app():
    application = create_app("application.config.TestConfig")
    application.config["SERVER_NAME"] = "127.0.0.1"

    with application.app_context():
        db.create_all()
        organisation = Organisation(
            name="Somewhere Borough Council",
            organisation=slugify("Somewhere Borough Council"),
            website="http://www.somewhere-borough-council.gov.uk",
        )
        db.session.add(organisation)
        db.session.commit()

    yield application

    with application.app_context():
        db.drop_all()


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def supporting_types(app):
    with app.app_context():
        import csv
        from pathlib import Path

        from application.extensions import db
        from application.models import LocalPlanDocumentType, LocalPlanEventType

        project_root = Path(__file__).parent.parent  # go up one level from tests dir

        # Load event types
        event_csv_path = project_root / "data" / "local-plan-event.csv"
        with open(event_csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                event_type = LocalPlanEventType(
                    name=row["name"],
                    reference=row["reference"],
                    description=row["description"],
                )
                db.session.add(event_type)

        # Load document types
        doc_csv_path = project_root / "data" / "local-plan-document-types.csv"
        with open(doc_csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                doc_type = LocalPlanDocumentType(
                    reference=row["reference"], name=row["name"]
                )
                db.session.add(doc_type)

        db.session.commit()


@pytest.fixture(scope="session")
def test_data(app, supporting_types):
    with app.app_context():
        organisation = Organisation.query.filter_by(
            name="Somewhere Borough Council"
        ).first()
        local_plan = LocalPlan(
            reference="some-where-local-plan", name="Somewhere Local Plan"
        )
        organisation.local_plans.append(local_plan)
        db.session.add(organisation)
        db.session.commit()
