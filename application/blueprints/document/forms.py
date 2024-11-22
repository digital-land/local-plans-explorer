from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    RadioField,
    SelectMultipleField,
    StringField,
    TextAreaField,
)
from wtforms.validators import URL, DataRequired, Optional, Regexp, ValidationError

from application.models import Status


class DocumentForm(FlaskForm):
    name = StringField("Name of supporting document", validators=[DataRequired()])
    description = TextAreaField("Brief description of supporting document")
    documentation_url = StringField(
        "URL for document information",
        validators=[
            Optional(),
            URL(),
            Regexp("^https?://", message="URL must start with http or https"),
        ],
    )
    document_url = StringField(
        "Document URL",
        validators=[
            DataRequired(),
            URL(),
            Regexp("^https?://", message="URL must start with http or https"),
        ],
    )
    organisations = StringField("Organisation", validators=[Optional()])
    document_types = SelectMultipleField(
        "Select one or more document types", validators=[Optional()]
    )
    for_publication = BooleanField("For publication", validators=[Optional()])


class EditDocumentForm(DocumentForm):
    status = RadioField("Status", validators=[Optional()])

    def __init__(self, *args, document=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.document = document

    def validate_status(self, field):
        error = "Can't set status to 'For platform' as the local plan status is '{}'"
        if field.data == Status.FOR_PLATFORM.name:
            if self.document and self.document.plan.status not in [
                Status.FOR_PLATFORM,
                Status.EXPORTED,
            ]:
                msg = error.format(self.document.plan.status.value)
                raise ValidationError(msg)
