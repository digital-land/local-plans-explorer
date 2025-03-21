from flask_wtf import FlaskForm
from shapely import wkt
from shapely.geometry import MultiPolygon, Polygon, mapping
from wtforms import RadioField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional, ValidationError

# from application.models import Status


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
    geometry_type = RadioField(
        "Geometry format",
        choices=[("wkt", "WKT (Well-Known Text)"), ("geojson", "GeoJSON")],
        validators=[DataRequired()],
        description="Choose the format you want to use to input the boundary",
    )
    geometry = TextAreaField(
        "Plan boundary geometry as WKT",
        validators=[Optional(), validate_geometry],
        description="Enter the boundary geometry in WKT format (MULTIPOLYGON or POLYGON)",
    )
    geojson = TextAreaField(
        "Plan boundary geometry as GeoJSON",
        validators=[Optional()],
        description="Enter the boundary geometry in GeoJSON format",
    )
    description = TextAreaField("Brief description of boundary")
    organisations = StringField("Organisation", validators=[Optional()])

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        if self.geometry_type.data == "wkt" and not self.geometry.data:
            self.geometry.errors.append(
                "WKT geometry is required when WKT format is selected"
            )
            return False

        if self.geometry_type.data == "geojson" and not self.geojson.data:
            self.geojson.errors.append(
                "GeoJSON is required when GeoJSON format is selected"
            )
            return False

        return True


class EditBoundaryForm(BoundaryForm):
    status = RadioField("Status", validators=[Optional()])

    def __init__(self, *args, boundary=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.boundary = boundary
        self.geometry_type.validators = [Optional()]

    def validate(self, extra_validators=None):
        # First validate all fields with their own validators
        if not super(FlaskForm, self).validate(extra_validators=extra_validators):
            return False

        # Only validate geometry if user has selected a geometry type
        if self.geometry_type.data:
            if self.geometry_type.data == "wkt" and not self.geometry.data:
                self.geometry.errors.append(
                    "WKT geometry is required when WKT format is selected"
                )
                return False

            if self.geometry_type.data == "geojson" and not self.geojson.data:
                self.geojson.errors.append(
                    "GeoJSON is required when GeoJSON format is selected"
                )
                return False

        # Validate status if provided
        # if self.status.data == Status.FOR_PLATFORM.name:
        #     if self.boundary and self.boundary.local_plans[0].status not in [
        #         Status.FOR_PLATFORM,
        #         Status.EXPORTED,
        #     ]:
        #         msg = "Can't set status to 'For platform' as the local plan status is '{}'"
        #         msg = msg.format(self.boundary.local_plans[0].status.value)
        #         self.status.errors.append(msg)
        #         return False

        return True
