from datetime import datetime

from flask import render_template, request
from flask_wtf import FlaskForm
from markupsafe import Markup
from wtforms import Field, SelectField, TextAreaField, ValidationError
from wtforms.validators import DataRequired, Optional


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
        self.errors = []
        self._part_errors = []

    def process_data(self, value):
        """Process the Python data applied to this field.
        This will be called during form construction by the form's `kwargs` or
        `obj` argument.
        """
        if value:
            # Handle string date from database
            if isinstance(value, str):
                try:
                    parts = value.split("-")
                    if len(parts) == 3:
                        self.data = {
                            "year": parts[0],
                            "month": str(int(parts[1])),  # Remove leading zeros
                            "day": str(int(parts[2])),  # Remove leading zeros
                        }
                    elif len(parts) == 2:
                        self.data = {
                            "year": parts[0],
                            "month": str(int(parts[1])),
                            "day": "",
                        }
                    else:
                        self.data = {"year": parts[0], "month": "", "day": ""}
                except (ValueError, IndexError):
                    self.data = {"day": "", "month": "", "year": ""}
            else:
                self.data = {"day": "", "month": "", "year": ""}
        else:
            self.data = {"day": "", "month": "", "year": ""}

    def _value(self):
        if self.data:
            return {
                "day": self.data.get("day", ""),
                "month": self.data.get("month", ""),
                "year": self.data.get("year", ""),
            }
        return {"day": "", "month": "", "year": ""}

    def process_formdata(self, valuelist):
        """Process data received over the wire from a form."""
        self.data = {
            "day": request.form.get(f"{self.name}_day", "").strip(),
            "month": request.form.get(f"{self.name}_month", "").strip(),
            "year": request.form.get(f"{self.name}_year", "").strip(),
        }

    def pre_validate(self, form):
        day = self.data.get("day", "")
        month = self.data.get("month", "")
        year = self.data.get("year", "")

        # Reset errors
        self._part_errors = []
        self.errors = []

        # Year is required
        if not year:
            self._add_error("Year is required", "year")
            return False

        # Validate dependencies
        if day and not month:
            self._add_error("Month is required when day is provided", "month")
            return False

        if (day or month) and not year:
            self._add_error("Year is required when month or day is provided", "year")
            return False

        # Validate year format
        if year:
            if not year.isdigit() or len(year) != 4:
                self._add_error("Year must be in YYYY format", "year")
                return False

        # Validate month
        if month:
            try:
                month_int = int(month)
                if not 1 <= month_int <= 12:
                    self._add_error("Month must be between 1 and 12", "month")
                    return False
            except ValueError:
                self._add_error("Month must be a number", "month")
                return False

        # Validate day
        if day:
            try:
                day_int = int(day)
                if not 1 <= day_int <= 31:
                    self._add_error("Day must be between 1 and 31", "day")
                    return False

                # Validate complete date if we have all parts
                if year and month:
                    try:
                        datetime(int(year), int(month), day_int)
                    except ValueError:
                        self._add_error(f"Invalid day for {month}/{year}", "day")
                        return False
            except ValueError:
                self._add_error("Day must be a number", "day")
                return False

        return True

    def _add_error(self, message, part):
        error = DatePartValidationError(message, part=part)
        self._part_errors.append(error)
        self.errors.append(str(error))

    def get_errors_with_parts(self):
        """Return list of errors with their associated parts"""
        return [
            {"message": str(error), "part": error.part} for error in self._part_errors
        ]

    def validate(self, form, extra_validators=None):
        self._part_errors = []  # Reset errors
        self.errors = []  # Reset errors
        success = self.pre_validate(form)
        if not success:
            # Ensure errors are propagated to the form level
            self.errors = [str(error) for error in self._part_errors]
        return success


class EventForm(FlaskForm):
    event_type = SelectField("Local plan event type", validators=[DataRequired()])
    event_date = DatePartField("Event date", validators=[Optional()])
    notes = TextAreaField("Notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Always set choices when form is instantiated
        self.event_type.choices = self._get_event_choices()

    def process(self, formdata=None, obj=None, **kwargs):
        # First set the choices
        self.event_type.choices = self._get_event_choices()

        # If we have an obj (like a LocalPlanEvent), convert its event type reference
        if obj is not None and hasattr(obj, "local_plan_event_type_reference"):
            # Set the event type value directly
            kwargs["event_type"] = obj.local_plan_event_type_reference

        # Now call the parent process method
        super().process(formdata, obj, **kwargs)

    @staticmethod
    def _get_event_choices():
        from application.models import LocalPlanEventType

        return [("", "")] + [
            (evt.reference, evt.name)
            for evt in LocalPlanEventType.query.order_by(LocalPlanEventType.name).all()
        ]

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
