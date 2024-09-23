import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Date, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db


class PublicationStatus(Enum):
    DRAFT = "Draft"
    READY_FOR_PUBLICATION = "Ready for publication"
    PUBLISHED = "Published"


class DateModel(db.Model):
    __abstract__ = True

    entry_date: Mapped[datetime.date] = mapped_column(
        Date, default=datetime.datetime.today
    )
    start_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    end_date: Mapped[Optional[datetime.date]] = mapped_column(Date)


plan_organisation = db.Table(
    "plan_organisation",
    db.Column("local_plan", Text, ForeignKey("local_plan.reference"), primary_key=True),
    db.Column(
        "organisation", Text, ForeignKey("organisation.organisation"), primary_key=True
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
        "local_plan_document",
        Text,
        ForeignKey("local_plan_document.reference"),
        primary_key=True,
    ),
    db.Column(
        "organisation", Text, ForeignKey("organisation.organisation"), primary_key=True
    ),
)


class BaseModel(DateModel):
    __abstract__ = True

    reference: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)


class LocalPlanBoundary(BaseModel):
    __tablename__ = "local_plan_boundary"

    plan_boundary_type: Mapped[Optional[str]] = mapped_column(Text)
    geometry: Mapped[Optional[str]] = mapped_column(Text)

    organisations = db.relationship(
        "Organisation",
        secondary=boundary_organisation,
        lazy="subquery",
        back_populates="local_plan_boundaries",
    )

    local_plans: Mapped[List["LocalPlan"]] = relationship(
        back_populates="local_plan_boundary_obj"
    )


class LocalPlan(BaseModel):
    __tablename__ = "local_plan"

    period_start_date: Mapped[Optional[int]] = mapped_column(Integer)
    period_end_date: Mapped[Optional[int]] = mapped_column(Integer)
    documentation_url: Mapped[Optional[str]] = mapped_column(Text)
    adopted_date: Mapped[Optional[str]] = mapped_column(Text)

    local_plan_boundary: Mapped[Optional[str]] = mapped_column(
        ForeignKey("local_plan_boundary.reference")
    )

    publication_status: Mapped[PublicationStatus] = mapped_column(
        ENUM(PublicationStatus), default=PublicationStatus.DRAFT
    )

    local_plan_boundary_obj: Mapped["LocalPlanBoundary"] = relationship(
        back_populates="local_plans"
    )

    documents: Mapped[List["LocalPlanDocument"]] = relationship(
        back_populates="local_plan_obj"
    )

    organisations = db.relationship(
        "Organisation",
        secondary=plan_organisation,
        lazy="subquery",
        back_populates="local_plans",
    )


class LocalPlanDocument(BaseModel):
    __tablename__ = "local_plan_document"

    plan_boundary_type: Mapped[Optional[str]] = mapped_column(Text)
    geometry: Mapped[Optional[str]] = mapped_column(Text)
    documentation_url: Mapped[Optional[str]] = mapped_column(Text)
    document_url: Mapped[Optional[str]] = mapped_column(Text)
    document_types: Mapped[Optional[list]] = mapped_column(ARRAY(Text))

    local_plan: Mapped[str] = mapped_column(ForeignKey("local_plan.reference"))
    local_plan_obj: Mapped["LocalPlan"] = relationship(back_populates="documents")

    organisations = db.relationship(
        "Organisation",
        secondary=document_organisation,
        lazy="subquery",
        back_populates="local_plan_documents",
    )


class Organisation(DateModel):
    __tablename__ = "organisation"

    organisation: Mapped[str] = mapped_column(Text, primary_key=True)
    local_authority_type: Mapped[Optional[str]] = mapped_column(Text)
    name: Mapped[Optional[dict]] = mapped_column(Text)
    official_name: Mapped[Optional[dict]] = mapped_column(Text)
    geometry: Mapped[Optional[dict]] = mapped_column(Text)
    geojson: Mapped[Optional[dict]] = mapped_column(JSONB)
    point: Mapped[Optional[str]] = mapped_column(Text)

    local_plan_documents = db.relationship(
        "LocalPlanDocument",
        secondary=document_organisation,
        lazy="subquery",
        back_populates="organisations",
    )

    local_plans = db.relationship(
        "LocalPlan",
        secondary=plan_organisation,
        lazy="subquery",
        back_populates="organisations",
    )

    local_plan_boundaries = db.relationship(
        "LocalPlanBoundary",
        secondary=boundary_organisation,
        lazy="subquery",
        back_populates="organisations",
    )
