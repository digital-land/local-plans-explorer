from flask_wtf import FlaskForm
from shapely import wkt
from shapely.geometry import MultiPolygon, Polygon, mapping
from wtforms import RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional, ValidationError

from application.models import Status


def validate_geometry(form, field):
    if not field.data:
        return

    try:
        # Try to parse as WKT
        geometry = wkt.loads(field.data)

        # Ensure it's a MultiPolygon
        if not isinstance(geometry, MultiPolygon):
            if isinstance(geometry, Polygon):
                geometry = MultiPolygon([geometry])
            else:
                raise ValidationError("Geometry must be a MultiPolygon or Polygon")

        # Store the parsed geometry for later use
        field.parsed_geometry = geometry

        # Try to convert to GeoJSON
        try:
            geojson = mapping(geometry)
            field.parsed_geojson = {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": geojson, "properties": {}}
                ],
            }
        except Exception as e:
            raise ValidationError(f"Failed to convert geometry to GeoJSON: {str(e)}")

    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Invalid WKT geometry: {str(e)}")


class BoundaryForm(FlaskForm):
    name = StringField("Name of boundary", validators=[DataRequired()])
    geometry = TextAreaField(
        "Plan boundary geometry as WKT",
        validators=[Optional(), validate_geometry],
        description="Enter the boundary geometry in WKT format (MULTIPOLYGON or POLYGON)",
    )
    geojson = TextAreaField(
        "Plan boundary geometry as GeoJSON",
        validators=[Optional()],
        description="Or provide the boundary geometry in GeoJSON format",
    )
    description = TextAreaField("Brief description of boundary")
    organisations = StringField("Organisation", validators=[Optional()])

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        # Ensure at least one of geometry or geojson is provided
        if not self.geometry.data and not self.geojson.data:
            self.geometry.errors.append(
                "Either WKT geometry or GeoJSON must be provided"
            )
            return False

        return True


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
