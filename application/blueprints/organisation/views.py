from flask import Blueprint, abort, redirect, render_template, request, url_for

from application.models import Organisation
from application.utils import get_planning_organisations

organisation = Blueprint("organisation", __name__, url_prefix="/organisation")


@organisation.route("/")
def organisations():
    if "organisation" in request.args:
        lpa = request.args.get("organisation")
        print(lpa)
        return redirect(
            url_for("organisation.organisation", reference=f"local-authority-eng:{lpa}")
        )

    orgs = get_planning_organisations()
    return render_template("organisation/index.html", organisations=orgs)


@organisation.route("/<string:reference>")
def get_organisation(reference):
    org = Organisation.query.get(reference)
    if org is None:
        return abort(404)
    return render_template("organisation/organisation.html", organisation=org)
