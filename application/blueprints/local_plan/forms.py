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
            Regexp("^https?://", message="URL must start with http or https"),
        ],
    )

    adopted_date_year = StringField("Adopted date year", validators=[Optional()])
    adopted_date_month = StringField("Adopted date month", validators=[Optional()])
    adopted_date_day = StringField("Adopted date day", validators=[Optional()])

    lds_published_date_year = StringField("LDS published year", validators=[Optional()])
    lds_published_date_month = StringField(
        "LDS published month", validators=[Optional()]
    )
    lds_published_date_day = StringField("LDS published day", validators=[Optional()])

    status = RadioField("Status", validators=[Optional()])


class DatePartsInputWidget:
    def __call__(self, field, **kwargs):
        # Get the errors with parts from the field
        errors_with_parts = field.get_errors_with_parts()
        # Create a dict of which parts have errors
        error_parts = {error["part"]: error["message"] for error in errors_with_parts}

        return Markup(
            render_template(
                "partials/date-parts-form.html",
                field=field,
                error_parts=error_parts,
                **kwargs,
            )
        )


class DatePartValidationError(ValidationError):
    def __init__(self, message, part=None):
        super().__init__(message)
        self.part = part  # 'day', 'month', or 'year'


class DatePartField(Field):
    widget = DatePartsInputWidget()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = []  # Initialize errors as a list instead of tuple
        self._errors_with_parts = []

    def _value(self):
        if self.data:
            return {
                "day": self.data.get("day", ""),
                "month": self.data.get("month", ""),
                "year": self.data.get("year", ""),
            }
        return {"day": "", "month": "", "year": ""}

    def process_formdata(self, valuelist):
        # Get raw input values without stripping yet
        raw_day = request.form.get(f"{self.name}_day", "")
        raw_month = request.form.get(f"{self.name}_month", "")
        raw_year = request.form.get(f"{self.name}_year", "")

        # Store raw values first
        self.data = {
            "day": raw_day.strip(),
            "month": raw_month.strip(),
            "year": raw_year.strip(),
        }

    def pre_validate(self, form):
        """Validate the date parts before the form-level validation"""
        day_str = self.data.get("day", "")
        month_str = self.data.get("month", "")
        year_str = self.data.get("year", "")

        # Collect all errors
        errors = []

        # If all fields are empty, that's valid
        if not any([day_str, month_str, year_str]):
            return True

        # Validate year if provided
        if year_str:
            if not year_str.isdigit() or len(year_str) != 4:
                errors.append(
                    DatePartValidationError("Year must be in YYYY format", part="year")
                )
        else:
            if day_str or month_str:
                errors.append(
                    DatePartValidationError(
                        "Year is required if day or month is provided", part="year"
                    )
                )

        # Validate month if provided
        if month_str:
            if not month_str.isdigit():
                errors.append(
                    DatePartValidationError(
                        "Month must be a number between 1 and 12", part="month"
                    )
                )
            else:
                month = int(month_str)
                if not (1 <= month <= 12):
                    errors.append(
                        DatePartValidationError(
                            "Month must be a number between 1 and 12", part="month"
                        )
                    )
        else:
            if day_str:
                errors.append(
                    DatePartValidationError(
                        "Month is required when day is provided", part="month"
                    )
                )

        # Validate day if provided
        if day_str:
            if not day_str.isdigit():
                errors.append(
                    DatePartValidationError(
                        "Day must be a number between 1 and 31", part="day"
                    )
                )
            else:
                day = int(day_str)
                if not (1 <= day <= 31):
                    errors.append(
                        DatePartValidationError(
                            "Day must be a number between 1 and 31", part="day"
                        )
                    )
                # Only check valid date if we have all parts and they're numeric
                elif (
                    year_str
                    and month_str
                    and year_str.isdigit()
                    and month_str.isdigit()
                ):
                    try:
                        datetime(int(year_str), int(month_str), day)
                    except ValueError:
                        errors.append(
                            DatePartValidationError(
                                f"Invalid day for {month_str}/{year_str}", part="day"
                            )
                        )

        # If we have any errors, raise them all
        if errors:
            # Store all errors
            self._errors_with_parts = [
                {"message": str(e), "part": e.part} for e in errors
            ]
            # Add all error messages to the field's errors list
            self.errors.extend(str(e) for e in errors)
            return False

        return True

    def get_errors_with_parts(self):
        """Return list of errors with their associated parts"""
        return getattr(self, "_errors_with_parts", [])

    def validate(self, form, extra_validators=None):
        self._errors_with_parts = []  # Reset errors
        self.errors = []  # Reset errors
        return self.pre_validate(form)


class BaseEventForm(FlaskForm):
    notes = TextAreaField("Notes")

    def get_error_summary(self):
        """Get summary of form errors for display"""
        errors = []
        for field in self:
            if isinstance(field, DatePartField):
                # Handle DatePartField errors specially
                for error in field.get_errors_with_parts():
                    errors.append(
                        {
                            "text": error["message"],
                            "href": f'#{field.name}_{error["part"]}',  # Links to specific input component
                        }
                    )
            elif field.errors:
                # Handle regular field errors
                for error in field.errors:
                    errors.append({"text": error, "href": f"#{field.name}"})
        return errors

    def validate(self, extra_validators=None) -> bool:
        """Custom validation that properly handles ValidationErrors from DatePartField"""
        # Run the standard form validation which includes field pre_validate
        if not super().validate(extra_validators=extra_validators):
            return False

        # If form is completely empty, that's valid
        if self.is_completely_empty():
            return True

        # Check if any DatePartFields have errors
        for field in self:
            if isinstance(field, DatePartField):
                try:
                    field.pre_validate(self)
                except ValidationError as e:
                    field.errors.append(str(e))
                    return False

        return True

    def is_completely_empty(self) -> bool:
        """Check if all fields in the form are empty"""
        for field in self:
            if field.name != "csrf_token":
                if isinstance(field.data, dict):
                    # For date fields, check if any of the values are non-empty
                    if any(value.strip() for value in field.data.values()):
                        return False
                elif field.data and str(field.data).strip():
                    return False
        return True


class EstimatedRegulation18Form(BaseEventForm):
    estimated_reg_18_draft_local_plan_published = DatePartField(
        "Draft local plan published", validators=[Optional()]
    )
    estimated_reg_18_public_consultation_start = DatePartField(
        "Regulation 18 consultation start", validators=[Optional()]
    )
    estimated_reg_18_public_consultation_end = DatePartField(
        "Regulation 18 consultation end", validators=[Optional()]
    )
    notes = TextAreaField("What does the consultation cover?", validators=[Optional()])

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.estimated_reg_18_draft_local_plan_published.process_data(
                obj.get("estimated_reg_18_draft_local_plan_published")
            )
            self.estimated_reg_18_public_consultation_start.process_data(
                obj.get("estimated_reg_18_public_consultation_start")
            )
            self.estimated_reg_18_public_consultation_end.process_data(
                obj.get("estimated_reg_18_public_consultation_end")
            )
            self.notes.data = obj.get("notes", "")


class EstimatedRegulation19Form(BaseEventForm):
    estimated_reg_19_publication_local_plan_published = DatePartField(
        "Publication local plan published", validators=[Optional()]
    )
    estimated_reg_19_public_consultation_start = DatePartField(
        "Regulation 19 consultation start", validators=[Optional()]
    )
    estimated_reg_19_public_consultation_end = DatePartField(
        "Regulation 19 consultation end", validators=[Optional()]
    )
    notes = TextAreaField("What does the consultation cover?", validators=[Optional()])

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.estimated_reg_19_publication_local_plan_published.process_data(
                obj.get("estimated_reg_19_publication_local_plan_published")
            )
            self.estimated_reg_19_public_consultation_start.process_data(
                obj.get("estimated_reg_19_public_consultation_start")
            )
            self.estimated_reg_19_public_consultation_end.process_data(
                obj.get("estimated_reg_19_public_consultation_end")
            )
            self.notes.data = obj.get("notes", "")


class EsitmatedExaminationAndAdoptionForm(BaseEventForm):
    estimated_submit_plan_for_examination = DatePartField(
        "Submit plan for examination", validators=[Optional()]
    )
    estimated_plan_adoption_date = DatePartField(
        "Adoption of local plan", validators=[Optional()]
    )

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.estimated_submit_plan_for_examination.process_data(
                obj.get("estimated_submit_plan_for_examination")
            )
            self.estimated_plan_adoption_date.process_data(
                obj.get("estimated_plan_adoption_date")
            )


class Regulation18Form(BaseEventForm):
    reg_18_draft_local_plan_published = DatePartField(
        "Draft local plan published", validators=[Optional()]
    )
    reg_18_public_consultation_start = DatePartField(
        "Regulation 18 consultation start", validators=[Optional()]
    )
    reg_18_public_consultation_end = DatePartField(
        "Regulation 18 consultation end", validators=[Optional()]
    )
    notes = TextAreaField("What does the consultation cover?", validators=[Optional()])

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.reg_18_draft_local_plan_published.process_data(
                obj.get("reg_18_draft_local_plan_published")
            )
            self.reg_18_public_consultation_start.process_data(
                obj.get("reg_18_public_consultation_start")
            )
            self.reg_18_public_consultation_end.process_data(
                obj.get("reg_18_public_consultation_end")
            )
            self.notes.data = obj.get("notes", "")


class Regulation19Form(BaseEventForm):
    reg_19_publication_local_plan_published = DatePartField(
        "Publication local plan published", validators=[Optional()]
    )
    reg_19_public_consultation_start = DatePartField(
        "Regulation 19 consultation start", validators=[Optional()]
    )
    reg_19_public_consultation_end = DatePartField(
        "Regulation 19 consultation end", validators=[Optional()]
    )
    notes = TextAreaField("What does the consultation cover?", validators=[Optional()])

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.reg_19_publication_local_plan_published.process_data(
                obj.get("reg_19_publication_local_plan_published")
            )
            self.reg_19_public_consultation_start.process_data(
                obj.get("reg_19_public_consultation_start")
            )
            self.reg_19_public_consultation_end.process_data(
                obj.get("reg_19_public_consultation_end")
            )
            self.notes.data = obj.get("notes", "")


class PlanningInspectorateExaminationForm(BaseEventForm):
    submit_plan_for_examination = DatePartField(
        "Plan submitted", validators=[Optional()]
    )
    planning_inspectorate_examination_start = DatePartField(
        "Examination start date", validators=[Optional()]
    )
    planning_inspectorate_examination_end = DatePartField(
        "Examination end date", validators=[Optional()]
    )

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.submit_plan_for_examination.process_data(
                obj.get("submit_plan_for_examination")
            )
            self.planning_inspectorate_examination_start.process_data(
                obj.get("planning_inspectorate_examination_start")
            )
            self.planning_inspectorate_examination_end.process_data(
                obj.get("planning_inspectorate_examination_end")
            )


class PlanningInspectorateFindingsForm(BaseEventForm):
    planning_inspectorate_found_sound = DatePartField(
        "Planning inspectorate found sound", validators=[Optional()]
    )
    inspector_report_published = DatePartField(
        "Report published", validators=[Optional()]
    )

    def __init__(self, obj=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if request.method == "GET" and obj:
            self.planning_inspectorate_found_sound.process_data(
                obj.get("planning_inspectorate_found_sound")
            )
            self.inspector_report_published.process_data(
                obj.get("inspector_report_published")
            )


def get_event_form(event_category, obj=None):
    match event_category:
        case EventCategory.ESTIMATED_REGULATION_18:
            return EstimatedRegulation18Form(obj=obj)
        case EventCategory.ESTIMATED_REGULATION_19:
            return EstimatedRegulation19Form(obj=obj)
        case EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION:
            return EsitmatedExaminationAndAdoptionForm(obj=obj)
        case EventCategory.REGULATION_18:
            return Regulation18Form(obj=obj)
        case EventCategory.REGULATION_19:
            return Regulation19Form(obj=obj)
        case EventCategory.PLANNING_INSPECTORATE_EXAMINATION:
            return PlanningInspectorateExaminationForm(obj=obj)
        case EventCategory.PLANNING_INSPECTORATE_FINDINGS:
            return PlanningInspectorateFindingsForm(obj=obj)
        case _:
            raise ValueError("Invalid event_category.")
