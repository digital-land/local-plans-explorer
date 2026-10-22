from unittest.mock import MagicMock, patch

import pytest

from application.factory import SSLifyExceptHealthCheck


@pytest.fixture
def request_mock():
    """Patch the request read by the subclass and by SSLify itself."""
    request = MagicMock(path="/")
    with patch("application.factory.request", request), patch(
        "flask_sslify.request", request
    ):
        yield request


@pytest.fixture
def sslify():
    # skip only reads the request and skip list, so no app is needed
    sslify = SSLifyExceptHealthCheck.__new__(SSLifyExceptHealthCheck)
    sslify.skip_list = None
    return sslify


@pytest.mark.parametrize(
    "path, expected",
    [("/", True), ("/local-plan/", False), ("/auth/login", False)],
)
def test_skip_only_skips_health_check_path(sslify, request_mock, path, expected):
    request_mock.path = path

    assert sslify.skip is expected


def test_skip_keeps_configured_skips(sslify, request_mock):
    sslify.skip_list = ["static"]
    request_mock.path = "/static/app.css"

    assert sslify.skip is True
