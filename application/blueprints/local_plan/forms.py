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

from application.models import EventCategory


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


class ConsultationForm(FlaskForm):
    draft_local_plan_published = DatePartField(
        "Draft local plan published", validators=[Optional()]
    )
    consultation_start = DatePartField(validators=[Optional()])
    consultation_end = DatePartField(validators=[Optional()])
    consultation_covers = TextAreaField(
        "What does the consultation cover?", validators=[Optional()]
    )

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = kwargs.get("event_category")
        if not self.category:
            raise ValueError("event_category is required.")
        self.consultation_stage = ConsultationForm.consultation_stage_number(
            self.category
        )
        self.consultation_start.label.text = (
            f"Regulation {self.consultation_stage} consultation start"
        )
        self.consultation_end.label.text = (
            f"Regulation {self.consultation_stage} consultation end"
        )

        if request.method == "GET" and obj:
            self.draft_local_plan_published.process_data(
                obj.get("draft_local_plan_published")
            )
            self.consultation_start.process_data(obj.get("consultation_start"))
            self.consultation_end.process_data(obj.get("consultation_end"))
            self.consultation_covers.data = obj.get("consultation_covers", "")

    @classmethod
    def consultation_stage_number(cls, category):
        match category:
            case EventCategory.ESTIMATED_REGULATION_18:
                return 18
            case EventCategory.ESTIMATED_REGULATION_19:
                return 19
            case _:
                return None

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        date_fields = [
            self.draft_local_plan_published,
            self.consultation_start,
            self.consultation_end,
        ]
        if not any(field.data.get("year") for field in date_fields if field.data):
            date_error = "At least one of the dates should have at least a year"
            self.draft_local_plan_published.errors.append(date_error)
            self.consultation_start.errors.append(date_error)
            self.consultation_end.errors.append(date_error)
            return False

        return True

    def get_error_summary(self):
        errors = []
        for field in [
            self.draft_local_plan_published,
            self.consultation_start,
            self.consultation_end,
        ]:
            if field.errors:
                errors.extend(field.errors)
        return errors[0] if errors else None


class ExaminationAndAdoptionForm(FlaskForm):
    submit_for_examination = DatePartField(
        "Submit plan for examination", validators=[Optional()]
    )
    adoption = DatePartField("Adoption of local plan", validators=[Optional()])

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.submit_for_examination.process_data(obj.get("submit_for_examination"))
            self.adoption.process_data(obj.get("adoption"))

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        date_fields = [
            self.submit_for_examination,
            self.adoption,
        ]
        if not any(field.data.get("year") for field in date_fields if field.data):
            date_error = "At least one of the dates should have at least a year"
            self.submit_for_examination.errors.append(date_error)
            self.adoption.errors.append(date_error)
            return False

        return True

    def get_error_summary(self):
        errors = []
        for field in [
            self.submit_for_examination,
            self.adoption,
        ]:
            if field.errors:
                errors.extend(field.errors)
        return errors[0] if errors else None
