from datetime import datetime

from flask import render_template, request
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
                "day": self.data.get("day", ""),
                "month": self.data.get("month", ""),
                "year": self.data.get("year", ""),
            }
        return {"day": "", "month": "", "year": ""}

    def process_formdata(self, valuelist):
        day_str = request.form.get(f"{self.name}_day", "")
        month_str = request.form.get(f"{self.name}_month", "")
        year_str = request.form.get(f"{self.name}_year", "")

        day = int(day_str) if day_str else None
        month = int(month_str) if month_str else None
        year = int(year_str) if year_str else None

        if (day or month) and not year:
            raise ValidationError(
                "Invalid date: a year is required if day or month is provided."
            )

        try:
            if year:
                if month and day:
                    datetime(year, month, day)
                elif month:
                    datetime(year, month, 1)
                else:
                    datetime(year, 1, 1)
            else:
                raise ValidationError("Invalid date: at least a year is required.")
        except ValueError:
            raise ValidationError(
                "Invalid date input: please check day, month, and year."
            )

        self.data = {
            "day": day_str,
            "month": month_str,
            "year": year_str,
        }

    def process_data(self, value):
        if isinstance(value, dict):
            self.data = {
                "day": value.get("day", ""),
                "month": value.get("month", ""),
                "year": value.get("year", ""),
            }
        else:
            self.data = {"day": "", "month": "", "year": ""}


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

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.draft_local_plan_published.process_data(
                obj.get("draft_local_plan_published")
            )
            self.regulation_18_start.process_data(obj.get("regulation_18_start"))
            self.regulation_18_end.process_data(obj.get("regulation_18_end"))
            self.consultation_covers.data = obj.get("consultation_covers", "")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        date_fields = [
            self.draft_local_plan_published,
            self.regulation_18_start,
            self.regulation_18_end,
        ]
        if not any(field.data.get("year") for field in date_fields if field.data):
            date_error = "At least one of the dates should have at least a year"
            self.draft_local_plan_published.errors.append(date_error)
            self.regulation_18_start.errors.append(date_error)
            self.regulation_18_end.errors.append(date_error)
            return False

        return True

    def get_error_summary(self):
        errors = []
        for field in [
            self.draft_local_plan_published,
            self.regulation_18_start,
            self.regulation_18_end,
        ]:
            if field.errors:
                errors.extend(field.errors)
        return errors[0] if errors else None


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
