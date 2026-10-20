from urllib.parse import parse_qs, urlparse

import pytest
import responses
from authlib.integrations.base_client.errors import MismatchingStateError

from application.factory import create_app

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_MEMBERS_URL = "https://api.github.com/orgs/digital-land/members/{login}"
GITHUB_GRANT_URL = "https://api.github.com/applications/test-client-id/grant"


def _start_login(client, next_url="/local-plan/"):
    """Setup: request /auth/login and return the OAuth state GitHub would send back."""
    response = client.get("/auth/login", query_string={"next": next_url})
    return parse_qs(urlparse(response.headers["Location"]).query)["state"][0]


def _mock_github(profile, membership_status=None):
    responses.post(
        GITHUB_TOKEN_URL,
        json={"access_token": "test-token", "token_type": "bearer"},
    )
    responses.get(GITHUB_USER_URL, json=profile)
    if membership_status is not None:
        responses.get(
            GITHUB_MEMBERS_URL.format(login=profile["login"]),
            status=membership_status,
        )


def test_login_redirects_to_github(auth_enabled_client):
    response = auth_enabled_client.get("/auth/login")

    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    query = parse_qs(location.query)
    assert location._replace(query="").geturl() == GITHUB_AUTHORIZE_URL
    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == ["https://localhost/auth/authorize"]
    assert query["scope"] == ["user:email read:org"]
    assert query["state"][0]


def test_login_remembers_safe_next_url(auth_enabled_client):
    auth_enabled_client.get("/auth/login", query_string={"next": "/local-plan/add"})

    with auth_enabled_client.session_transaction() as session:
        assert session["next"] == "/local-plan/add"


def test_login_replaces_unsafe_next_url_with_home(auth_enabled_client):
    auth_enabled_client.get(
        "/auth/login", query_string={"next": "https://evil.example/"}
    )

    with auth_enabled_client.session_transaction() as session:
        assert session["next"] == "/"


def test_login_skips_github_when_authentication_off(https_test_client):
    client = https_test_client(create_app("application.config.TestConfig"))

    response = client.get("/auth/login", query_string={"next": "/local-plan/"})

    assert response.status_code == 302
    assert response.headers["Location"] == "/local-plan/"


@responses.activate
def test_authorize_signs_in_digital_land_member(auth_enabled_client):
    state = _start_login(auth_enabled_client, next_url="/local-plan/add")
    _mock_github({"login": "octocat", "name": "Octo Cat"}, membership_status=204)

    response = auth_enabled_client.get(
        "/auth/authorize", query_string={"code": "test-code", "state": state}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/local-plan/add"
    with auth_enabled_client.session_transaction() as session:
        assert session["user"] == "Octo Cat"
        assert "next" not in session


@responses.activate
def test_authorize_uses_github_login_when_name_missing(auth_enabled_client):
    state = _start_login(auth_enabled_client)
    _mock_github({"login": "octocat", "name": None}, membership_status=204)

    auth_enabled_client.get(
        "/auth/authorize", query_string={"code": "test-code", "state": state}
    )

    with auth_enabled_client.session_transaction() as session:
        assert session["user"] == "octocat"


@responses.activate
def test_authorize_rejects_non_member_and_revokes_grant(auth_enabled_client):
    state = _start_login(auth_enabled_client)
    _mock_github({"login": "outsider", "name": "Outsider"}, membership_status=404)
    responses.delete(GITHUB_GRANT_URL, status=204)

    response = auth_enabled_client.get(
        "/auth/authorize", query_string={"code": "test-code", "state": state}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with auth_enabled_client.session_transaction() as session:
        assert "user" not in session
        assert session["_flashes"] == [
            (
                "message",
                "You must be a member of the digital-land organisation to log in",
            )
        ]
    revoke = next(c for c in responses.calls if c.request.method == "DELETE")
    assert revoke.request.url.startswith(GITHUB_GRANT_URL)
    assert revoke.request.headers["Authorization"].startswith("Basic ")


@responses.activate
def test_authorize_rejects_empty_github_profile(auth_enabled_client):
    state = _start_login(auth_enabled_client)
    _mock_github({})

    response = auth_enabled_client.get(
        "/auth/authorize", query_string={"code": "test-code", "state": state}
    )

    assert response.headers["Location"] == "/"
    with auth_enabled_client.session_transaction() as session:
        assert "user" not in session


@responses.activate
def test_authorize_rejects_mismatched_state(auth_enabled_client):
    _start_login(auth_enabled_client)

    # currently an unhandled error (a 500 outside tests) rather than a
    # redirect, but it must never sign the user in or call GitHub
    with pytest.raises(MismatchingStateError):
        auth_enabled_client.get(
            "/auth/authorize",
            query_string={"code": "test-code", "state": "forged-state"},
        )

    with auth_enabled_client.session_transaction() as session:
        assert "user" not in session
    assert len(responses.calls) == 0


def test_logout_clears_signed_in_user(auth_enabled_client):
    with auth_enabled_client.session_transaction() as session:
        session["user"] = "Octo Cat"
        session["next"] = "/local-plan/"

    response = auth_enabled_client.get("/auth/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    with auth_enabled_client.session_transaction() as session:
        assert "user" not in session
        assert "next" not in session
