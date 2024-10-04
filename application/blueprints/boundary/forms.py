from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class BoundaryForm(FlaskForm):
    name = StringField("Name of boundary", validators=[DataRequired()])
    geometry = TextAreaField(
        "Plan boundary geometry as WKT or geojson", validators=[DataRequired()]
    )
    description = TextAreaField("Brief description of supporting document")
    organisations = StringField("Organisation", validators=[Optional()])
    plan_boundary_type = StringField("Boundary type", validators=[Optional()])
