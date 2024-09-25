from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import URL, DataRequired, Optional, Regexp


class LocalPlanForm(FlaskForm):
    name = StringField("Name of plan", validators=[DataRequired()])
    organisations = StringField("Organisations", validators=[DataRequired()])
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
    documentation_url = StringField(
        "URL for plan information",
        validators=[
            Optional(),
            URL(),
            Regexp("^https?://", message="URL must start with http or https"),
        ],
    )
    adopted_date_year = StringField("Adopted date year", validators=[Optional()])
    adopted_date_month = StringField("Adopted date month", validators=[Optional()])
    adopted_date_day = StringField("Adopted date day", validators=[Optional()])
