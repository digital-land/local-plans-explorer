from flask_wtf import FlaskForm
from wtforms import RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional, ValidationError

from application.models import Status


class BoundaryForm(FlaskForm):
    name = StringField("Name of boundary", validators=[DataRequired()])
    geojson = TextAreaField(
        "Plan boundary geometry as geojson", validators=[DataRequired()]
    )
    description = TextAreaField("Brief description of boundary")
    organisations = StringField("Organisation", validators=[Optional()])


class EditBoundaryForm(BoundaryForm):
    status = RadioField("Status", validators=[Optional()])

    def __init__(self, *args, boundary=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.boundary = boundary

    def validate_status(self, field):
        error = "Can't set status to 'For platform' as the local plan status is '{}'"
        if field.data == Status.FOR_PLATFORM.name:
            if self.boundary and self.boundary.local_plans[0].status not in [
                Status.FOR_PLATFORM,
                Status.EXPORTED,
            ]:
                msg = error.format(self.boundary.local_plans[0].status.value)
                raise ValidationError(msg)
