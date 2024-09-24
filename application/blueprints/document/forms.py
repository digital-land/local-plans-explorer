from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, TextAreaField
from wtforms.validators import URL, DataRequired, Optional, Regexp


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
    document_types = StringField("Document type", validators=[Optional()])
    inlcude_in_dataset = BooleanField("Include in dataset", default=False)
