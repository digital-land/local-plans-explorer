import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db


class Status(Enum):
    FOR_REVIEW = "For review"
    FOR_PLATFORM = "For platform"
    NOT_FOR_PLATFORM = "Not for platform"
    EXPORTED = "Exported"


class DateModel(db.Model):
    __abstract__ = True

    entry_date: Mapped[datetime.date] = mapped_column(
        Date, default=datetime.datetime.today
    )
    start_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(Date, index=True)


local_plan_organisation = db.Table(
    "local_plan_organisation",
    db.Column(
        "local_plan",
        Text,
        ForeignKey("local_plan.reference"),
        primary_key=True,
        index=True,
    ),
    db.Column(
        "organisation",
        Text,
        ForeignKey("organisation.organisation"),
        primary_key=True,
        index=True,
    ),
)

boundary_organisation = db.Table(
    "boundary_organisation",
    db.Column(
        "local_plan_boundary",
        Text,
        ForeignKey("local_plan_boundary.reference"),
        primary_key=True,
    ),
    db.Column(
        "organisation", Text, ForeignKey("organisation.organisation"), primary_key=True
    ),
)

document_organisation = db.Table(
    "document_organisation",
    db.Column(
        "local_plan_document_reference",
        Text,
        ForeignKey("local_plan_document.reference"),
        nullable=False,
    ),
    db.Column(
        "organisation", Text, ForeignKey("organisation.organisation"), nullable=False
    ),
    db.PrimaryKeyConstraint(
        "local_plan_document_reference",
        "organisation",
    ),
)


class BaseModel(DateModel):
    __abstract__ = True

    reference: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)


class LocalPlanDocumentType(BaseModel):
    __tablename__ = "local_plan_document_type"


class LocalPlanBoundary(BaseModel):
    __tablename__ = "local_plan_boundary"

    geometry: Mapped[Optional[str]] = mapped_column(Text)

    geojson: Mapped[Optional[dict]] = mapped_column(JSONB)

    organisations = db.relationship(
        "Organisation",
        secondary=boundary_organisation,
        lazy="joined",
        back_populates="local_plan_boundaries",
    )

    local_plans: Mapped[List["LocalPlan"]] = relationship(back_populates="boundary")


class LocalPlan(BaseModel):
    __tablename__ = "local_plan"

    period_start_date: Mapped[Optional[int]] = mapped_column(Integer)
    period_end_date: Mapped[Optional[int]] = mapped_column(Integer)
    documentation_url: Mapped[Optional[str]] = mapped_column(Text)

    local_plan_boundary: Mapped[Optional[str]] = mapped_column(
        ForeignKey("local_plan_boundary.reference")
    )

    status: Mapped[Status] = mapped_column(ENUM(Status), default=Status.FOR_REVIEW)

    boundary: Mapped["LocalPlanBoundary"] = relationship(back_populates="local_plans")

    documents: Mapped[List["LocalPlanDocument"]] = relationship(
        back_populates="plan", lazy="select"
    )

    timetable: Mapped[List["LocalPlanTimetable"]] = relationship(
        back_populates="local_plan", lazy="select"
    )

    def ordered_events(self, reverse=True):
        from datetime import datetime

        def parse_date(date_str):
            if not date_str:
                return None

            # Try different date formats from most specific to least
            formats = ["%Y-%m-%d", "%Y-%m", "%Y"]
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None

        # Filter events with dates and parse them
        dated_events = [
            (event, parse_date(event.event_date))
            for event in self.timetable
            if event.event_date is not None and event.end_date is None
        ]

        # Sort by parsed date
        dated_events.sort(key=lambda x: x[1], reverse=reverse)

        # Return just the event objects
        return [event for event, _ in dated_events]

    @property
    def adopted_date(self):
        for event in self.timetable:
            if event.event_type.reference == "plan-adopted":
                return event.event_date
        return ""

    organisations = db.relationship(
        "Organisation",
        secondary=local_plan_organisation,
        lazy="select",
        back_populates="local_plans",
    )

    def is_joint_plan(self):
        return len(self.organisations) > 1

    # boundary status set on local plan as boundary is one to many from local_plan_boundary
    # to local_plan, therefore boundary is specific to a single local plan and therefore
    # approval needs to be set at the plan level
    boundary_status: Mapped[Optional[Status]] = mapped_column(
        ENUM(Status), default=Status.FOR_REVIEW
    )


class LocalPlanDocument(BaseModel):
    __tablename__ = "local_plan_document"

    local_plan: Mapped[str] = mapped_column(ForeignKey("local_plan.reference"))
    plan: Mapped["LocalPlan"] = relationship()

    documentation_url: Mapped[Optional[str]] = mapped_column(Text)
    document_url: Mapped[Optional[str]] = mapped_column(Text)
    document_types: Mapped[Optional[list]] = mapped_column(ARRAY(Text))

    organisations = db.relationship(
        "Organisation",
        secondary=document_organisation,
        lazy="select",
        back_populates="local_plan_documents",
    )

    status: Mapped[Status] = mapped_column(ENUM(Status), default=Status.FOR_REVIEW)

    def get_document_types(self):
        doc_types = (
            LocalPlanDocumentType.query.filter(
                LocalPlanDocumentType.reference.in_(self.document_types)
            )
            .order_by(LocalPlanDocumentType.name)
            .all()
        )
        return doc_types


class Organisation(DateModel):
    __tablename__ = "organisation"

    organisation: Mapped[str] = mapped_column(Text, primary_key=True)
    local_authority_type: Mapped[Optional[str]] = mapped_column(Text)
    name: Mapped[Optional[dict]] = mapped_column(Text, index=True)
    official_name: Mapped[Optional[dict]] = mapped_column(Text)
    geometry: Mapped[Optional[str]] = mapped_column(Text)
    geojson: Mapped[Optional[dict]] = mapped_column(JSONB)
    point: Mapped[Optional[str]] = mapped_column(Text)
    statistical_geography: Mapped[Optional[str]] = mapped_column(Text)
    website: Mapped[Optional[str]] = mapped_column(Text)

    local_plan_documents = db.relationship(
        "LocalPlanDocument",
        secondary=document_organisation,
        lazy="select",
        back_populates="organisations",
    )

    local_plans = db.relationship(
        "LocalPlan",
        secondary=local_plan_organisation,
        lazy="select",
        back_populates="organisations",
    )

    local_plan_boundaries = db.relationship(
        "LocalPlanBoundary",
        secondary=boundary_organisation,
        lazy="select",
        back_populates="organisations",
    )


class LocalPlanEventType(BaseModel):
    __tablename__ = "local_plan_event_type"


class LocalPlanTimetable(BaseModel):
    __tablename__ = "local_plan_timetable"

    event_data: Mapped[Optional[dict]] = mapped_column(MutableDict.as_mutable(JSONB))
    event_date: Mapped[Optional[str]] = mapped_column(Text)
    event_type: Mapped[Optional["LocalPlanEventType"]] = relationship()
    local_plan_event: Mapped[Optional[str]] = mapped_column(
        ForeignKey("local_plan_event_type.reference")
    )

    created_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )
    local_plan_reference: Mapped[str] = mapped_column(
        ForeignKey("local_plan.reference")
    )
    local_plan: Mapped["LocalPlan"] = relationship(back_populates="timetable")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    organisation: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organisation.organisation"), nullable=True
    )
    organisation_obj: Mapped["Organisation"] = relationship()

    def get_event_type_name(self, key):
        if key not in self.event_data:
            return ""
        event_type_refererence = key.replace("_", "-")
        event_type = LocalPlanEventType.query.get(event_type_refererence)
        if event_type is None:
            return ""
        return event_type.name
