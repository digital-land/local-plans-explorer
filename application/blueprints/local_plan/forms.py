from flask_wtf import FlaskForm
from wtforms import RadioField, StringField, TextAreaField, URLField, ValidationError
from wtforms.validators import DataRequired, Optional, Regexp


class LocalPlanForm(FlaskForm):
    def validate_period_start_date(form, field):
        if field.data and not field.data.isdigit():
            raise ValidationError("Start date must be numeric.")

    def validate_period_end_date(form, field):
        if field.data and not field.data.isdigit():
            raise ValidationError("End date must be numeric.")

    name = StringField("Name of plan", validators=[DataRequired()])
    organisations = StringField("Organisation", validators=[DataRequired()])
    description = TextAreaField("Brief description of plan", validators=[Optional()])
    period_start_date = StringField(
        "Plan start date",
        validators=[Optional()],
        description="The year the plan starts, for example, 2022",
    )
    period_end_date = StringField(
        "Plan end date",
        validators=[Optional()],
        description="The year the plan ends, for example, 2045",
    )
    documentation_url = URLField(
        "URL for plan information",
        validators=[
            DataRequired(),
            Regexp("^https?://", message="URL must start with http:// or https://"),
        ],
        render_kw={
            "hint": "For example, http://www.borough-council.gov.uk/the-local-plan"
        },
    )
    status = RadioField("Status", validators=[Optional()])
