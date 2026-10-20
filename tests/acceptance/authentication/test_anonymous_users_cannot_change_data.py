"""
Acceptance criteria: only signed-in members of digital-land can add, edit or
remove local plan data.

Every route has to require login unless its endpoint is listed in
PUBLIC_ENDPOINTS, so a new route is locked down unless someone deliberately
makes it public.
"""

import re

# endpoint -> why it's public
PUBLIC_ENDPOINTS = {
    "static": "Built CSS, JavaScript and images",
    "main.index": "Read-only",
    "main.stats": "Read-only",
    "main.randomiser": "Read-only",
    "local_plan.index": "Read-only",
    "local_plan.archived_plans": "Read-only",
    "local_plan.get_plan": "Read-only",
    "boundary.get_boundary": "Read-only",
    "document.get_document": "Read-only",
    "organisation.organisations": "Read-only",
    "organisation.get_organisation": "Read-only",
    "export.export_local_plans": "Downloaded by the data-export workflow",
    "export.export_local_plan_timetables": "Downloaded by the data-export workflow",
    "export.export_boundaries": "Downloaded by the data-export workflow",
    "export.export_documents": "Downloaded by the data-export workflow",
    "auth.login": "Needed to sign in",
    "auth.authorize": "Needed to sign in",
    "auth.logout": "Needed to sign out",
}


def _non_public_requests(app):
    """Every method of every route not in PUBLIC_ENDPOINTS, with dummy URL values."""
    for rule in app.url_map.iter_rules():
        if rule.endpoint in PUBLIC_ENDPOINTS:
            continue
        url = re.sub(r"<[^>]+>", "test-reference", rule.rule)
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            yield method, url, rule.endpoint


def test_anonymous_user_is_sent_to_login_for_every_non_public_route(
    auth_enabled_app, auth_enabled_client
):
    requests = list(_non_public_requests(auth_enabled_app))
    assert requests, "expected some routes to require login"

    unprotected = []
    for method, url, endpoint in requests:
        try:
            response = auth_enabled_client.open(url, method=method)
        except Exception as error:
            # the view ran (and failed without a database), so it isn't protected
            unprotected.append(
                f"{method} {url} ({endpoint}) raised {type(error).__name__}"
            )
            continue
        location = response.headers.get("Location", "")
        if response.status_code != 302 or not location.startswith("/auth/login"):
            unprotected.append(
                f"{method} {url} ({endpoint}) returned {response.status_code}"
            )

    assert unprotected == [], (
        "Routes reachable without signing in. Add @login_required, or add the "
        "endpoint to PUBLIC_ENDPOINTS if it should be public:\n"
        + "\n".join(unprotected)
    )


def test_public_endpoints_all_exist(auth_enabled_app):
    endpoints = {rule.endpoint for rule in auth_enabled_app.url_map.iter_rules()}

    assert set(PUBLIC_ENDPOINTS) - endpoints == set()
