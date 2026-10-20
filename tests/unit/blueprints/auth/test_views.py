from unittest.mock import MagicMock, patch

import pytest

from application.blueprints.auth.views import _make_next_url_safe


@pytest.fixture(autouse=True)
def flask_mocks():
    """Patch the Flask objects _make_next_url_safe uses.

    is_safe_url isn't mocked: it's a pure function and checking which URLs it
    accepts is the point of these tests.
    """
    with patch.multiple(
        "application.blueprints.auth.views",
        current_app=MagicMock(config={"SAFE_URLS": {"localhost"}}),
        url_for=MagicMock(return_value="/"),
    ):
        yield


@pytest.mark.parametrize(
    "next_url",
    ["/local-plan/", "http://localhost/local-plan/add"],
)
def test_make_next_url_safe_keeps_urls_on_safe_hosts(next_url):
    assert _make_next_url_safe(next_url) == next_url


@pytest.mark.parametrize(
    "next_url",
    [
        "https://evil.example/",
        "//evil.example/",
        "javascript:alert(1)",
    ],
)
def test_make_next_url_safe_replaces_unsafe_urls_with_home(next_url):
    assert _make_next_url_safe(next_url) == "/"


def test_make_next_url_safe_returns_home_when_next_url_missing():
    assert _make_next_url_safe(None) == "/"
