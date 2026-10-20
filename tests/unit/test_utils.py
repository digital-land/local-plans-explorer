from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from application.utils import login_required


@pytest.fixture
def flask_mocks():
    """Patch the Flask objects login_required uses.

    Defaults to an anonymous user with authentication on.
    """
    mocks = SimpleNamespace(
        current_app=MagicMock(config={"AUTHENTICATION_ON": True}),
        session={},
        request=MagicMock(url="http://localhost/local-plan/add"),
        redirect=MagicMock(return_value="redirect response"),
        url_for=MagicMock(return_value="/auth/login?next=local-plan-add"),
    )
    with patch.multiple("application.utils", **vars(mocks)):
        yield mocks


def test_login_required_redirects_anonymous_user_to_login(flask_mocks):
    view = MagicMock()

    response = login_required(view)()

    view.assert_not_called()
    flask_mocks.url_for.assert_called_once_with(
        "auth.login", next="http://localhost/local-plan/add"
    )
    flask_mocks.redirect.assert_called_once_with("/auth/login?next=local-plan-add")
    assert response == "redirect response"


def test_login_required_calls_view_for_signed_in_user(flask_mocks):
    flask_mocks.session["user"] = "Test User"
    view = MagicMock(return_value="view response")

    response = login_required(view)("some-plan", reference="some-document")

    view.assert_called_once_with("some-plan", reference="some-document")
    assert response == "view response"


def test_login_required_calls_view_when_authentication_off(flask_mocks):
    flask_mocks.current_app.config["AUTHENTICATION_ON"] = False
    view = MagicMock(return_value="view response")

    response = login_required(view)()

    assert response == "view response"
    flask_mocks.redirect.assert_not_called()


def test_login_required_redirects_when_authentication_setting_missing(flask_mocks):
    del flask_mocks.current_app.config["AUTHENTICATION_ON"]
    view = MagicMock()

    login_required(view)()

    view.assert_not_called()
    flask_mocks.redirect.assert_called_once()


def test_login_required_keeps_view_name():
    # Flask names endpoints after the view function, so the wrapper must keep it
    def edit_plan():
        pass

    assert login_required(edit_plan).__name__ == "edit_plan"
