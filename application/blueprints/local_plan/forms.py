from datetime import datetime

from flask import render_template
from flask_wtf import FlaskForm
from markupsafe import Markup
from wtforms import (
    Field,
    RadioField,
    StringField,
    TextAreaField,
    URLField,
    ValidationError,
)
from wtforms.validators import DataRequired, Optional, Regexp


class LocalPlanForm(FlaskForm):
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
            Regexp("^https?://", message="URL must start with http or https"),
        ],
    )
    adopted_date_year = StringField("Adopted date year", validators=[Optional()])
    adopted_date_month = StringField("Adopted date month", validators=[Optional()])
    adopted_date_day = StringField("Adopted date day", validators=[Optional()])

    status = RadioField("Status", validators=[Optional()])


class DatePartsInputWidget:
    def __call__(self, field, **kwargs):
        return Markup(
            render_template("partials/date-parts-form.html", field=field, **kwargs)
        )


class DatePartField(Field):
    widget = DatePartsInputWidget()

    def _value(self):
        if self.data:
            return {
                "day": self.data.day,
                "month": self.data.month,
                "year": self.data.year,
            }
        return {"day": "", "month": "", "year": ""}

    def process_formdata(self, valuelist):
        if len(valuelist) != 3:
            raise ValidationError("Invalid date input.")

        day_str, month_str, year_str = valuelist
        day = int(day_str) if day_str else None
        month = int(month_str) if month_str else None
        year = int(year_str) if year_str else None

        if year:
            if month and day:
                try:
                    self.data = datetime(year, month, day)
                except ValueError:
                    raise ValidationError(
                        "Invalid date: year, month, or day is out of range."
                    )
            elif month:
                try:
                    self.data = datetime(year, month, 1)
                except ValueError:
                    raise ValidationError(
                        "Invalid date: year or month is out of range."
                    )
            else:
                self.data = datetime(year, 1, 1)
        else:
            raise ValidationError("Invalid date: at least a year is required.")

    def process_data(self, value):
        if value:
            self.data = value
        else:
            self.data = None


class Regulation18Form(FlaskForm):
    draft_local_plan_published = DatePartField(
        "Draft local plan published", validators=[Optional()]
    )
    regulation_18_start = DatePartField(
        "Regulation 18 consultation start", validators=[Optional()]
    )
    regulation_18_end = DatePartField(
        "Regulation 18 consultation end", validators=[Optional()]
    )
    consultation_covers = TextAreaField(
        "What does the consultation cover?", validators=[Optional()]
    )


class Regulation19Form(FlaskForm):
    draft_local_plan_published = DatePartField(
        "Draft local plan published", validators=[Optional()]
    )
    regulation_19_start = DatePartField(
        "Regulation 19 consultation start", validators=[Optional()]
    )
    regulation_19_end = DatePartField(
        "Regulation 19 consultation end", validators=[Optional()]
    )
    consultation_covers = TextAreaField(
        "Consultation coverage", validators=[Optional()]
    )
