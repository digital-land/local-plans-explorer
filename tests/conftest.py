import pytest
from slugify import slugify

from application.extensions import db
from application.factory import create_app
from application.models import Organisation


@pytest.fixture(scope="session")
def app():
    application = create_app("application.config.TestConfig")
    application.config["SERVER_NAME"] = "127.0.0.1:5050"

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
