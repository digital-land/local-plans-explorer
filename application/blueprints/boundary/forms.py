from flask_wtf import FlaskForm
from wtforms import RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class BoundaryForm(FlaskForm):
    name = StringField("Name of boundary", validators=[DataRequired()])
    geojson = TextAreaField(
        "Plan boundary geometry as geojson", validators=[DataRequired()]
    )
    description = TextAreaField("Brief description of supporting document")
    organisations = StringField("Organisation", validators=[Optional()])


class EditBoundaryForm(BoundaryForm):
    status = RadioField("Status", validators=[Optional()])
