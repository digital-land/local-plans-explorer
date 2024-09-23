import requests
from flask.cli import AppGroup
from sqlalchemy.inspection import inspect

from application.extensions import db
from application.models import Organisation

data_cli = AppGroup("data")


@data_cli.command("load-orgs")
def load_orgs():
    url = "https://datasette.planning.data.gov.uk/digital-land/organisation.json?_shape=array"
    orgs = []
    columns = set([column.name for column in inspect(Organisation).c])
    while url:
        resp = requests.get(url)
        try:
            url = resp.links.get("next").get("url")
        except AttributeError:
            url = None
        orgs.extend(resp.json())

    for org in orgs:
        if not org["organisation"]:
            print("Skipping invalid org", org["name"])
            continue
        if org["end_date"]:
            print("Skipping end dated org", org["organisation"])
            continue
        try:
            org_obj = Organisation.query.get(org["organisation"])
            if org_obj is None:
                org_obj = Organisation()
                for key, value in org.items():
                    if key in columns:
                        v = value if value else None
                        setattr(org_obj, key, v)
                db.session.add(org_obj)
                db.session.commit()
        except Exception as e:
            print(e)
            continue
