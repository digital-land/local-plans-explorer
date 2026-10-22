"""
Acceptance criteria: visitors are always on https, and the load balancer health
check keeps passing.

TLS ends at the load balancer, which sets X-Forwarded-Proto on visitors'
requests. Its health check requests / over plain http with no X-Forwarded-Proto
and must get a 200, or the service is marked unhealthy.
"""

import pytest

from application.factory import create_app

HEALTH_CHECK = {"User-Agent": "ELB-HealthChecker/2.0"}


@pytest.fixture
def production_client():
    # imported here as application.config reads env vars set by load_dotenv
    # when application.factory is imported
    from application.config import Config

    # the production config, as the debug config never redirects
    class ProductionConfig(Config):
        AUTHENTICATION_ON = False

    return create_app(ProductionConfig).test_client()


def test_health_check_on_home_page_is_served_over_http(production_client):
    response = production_client.get("/", headers=HEALTH_CHECK)

    assert response.status_code == 200


def test_plain_http_request_is_redirected_to_https(production_client):
    response = production_client.get("/auth/logout")

    assert response.status_code == 302
    assert response.headers["Location"] == "https://localhost/auth/logout"


def test_request_through_https_load_balancer_is_not_redirected(production_client):
    response = production_client.get(
        "/auth/logout", headers={"X-Forwarded-Proto": "https"}
    )

    # logout's own redirect home, not a redirect to https
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
