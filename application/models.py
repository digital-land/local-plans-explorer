import datetime
import re
import uuid
from collections import OrderedDict
from enum import Enum
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db


class Status(Enum):
    FOR_REVIEW = "For review"
    FOR_PLATFORM = "For platform"
    NOT_FOR_PLATFORM = "Not for platform"
    EXPORTED = "Exported"


class DocumentStatus(Enum):
    ACCEPT = "Accept"
    REJECT = "Reject"


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
    db.Column("local_plan_document_reference", Text, nullable=False),
    db.Column("local_plan_document_local_plan", Text, nullable=False),
    db.Column(
        "organisation", Text, ForeignKey("organisation.organisation"), nullable=False
    ),
    db.PrimaryKeyConstraint(
        "local_plan_document_reference",
        "local_plan_document_local_plan",
        "organisation",
    ),
    db.ForeignKeyConstraint(
        ["local_plan_document_reference", "local_plan_document_local_plan"],
        ["local_plan_document.reference", "local_plan_document.local_plan"],
        ondelete="CASCADE",
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

    plan_boundary_type: Mapped[Optional[str]] = mapped_column(Text)
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
    adopted_date: Mapped[Optional[str]] = mapped_column(Text)

    local_plan_boundary: Mapped[Optional[str]] = mapped_column(
        ForeignKey("local_plan_boundary.reference")
    )

    status: Mapped[Status] = mapped_column(ENUM(Status), default=Status.FOR_REVIEW)

    boundary: Mapped["LocalPlanBoundary"] = relationship(back_populates="local_plans")

    documents: Mapped[List["LocalPlanDocument"]] = relationship(
        back_populates="plan", lazy="select"
    )

    organisations = db.relationship(
        "Organisation",
        secondary=local_plan_organisation,
        lazy="joined",
        back_populates="local_plans",
    )

    # boundary status set on local plan as boundary is one to many from local_plan_boundary
    # to local_plan, therefore boundary is specific to a single local plan and therefore
    # approval needs to be set at the plan level
    boundary_status: Mapped[Optional[Status]] = mapped_column(
        ENUM(Status), default=Status.FOR_REVIEW
    )

    candidate_documents: Mapped[List["CandidateDocument"]] = relationship(
        back_populates="plan", lazy="joined"
    )

    timetable: Mapped[Optional["LocalPlanTimetable"]] = relationship(
        back_populates="local_plan_obj", uselist=False
    )

    def unprocessed_canidate_documents(self):
        return CandidateDocument.query.filter(
            CandidateDocument.local_plan == self.reference,
            CandidateDocument.status.is_(None),
        ).all()


class LocalPlanDocument(BaseModel):
    __tablename__ = "local_plan_document"

    local_plan: Mapped[str] = mapped_column(
        ForeignKey("local_plan.reference"), primary_key=True
    )
    plan: Mapped["LocalPlan"] = relationship(back_populates="documents", lazy="joined")

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


class CandidateDocument(db.Model):
    __tablename__ = "candidate_document"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[Optional[str]] = mapped_column(Text)
    local_plan: Mapped[str] = mapped_column(ForeignKey("local_plan.reference"))
    plan: Mapped["LocalPlan"] = relationship(
        back_populates="candidate_documents", lazy="joined"
    )
    documentation_url: Mapped[Optional[str]] = mapped_column(Text)
    document_url: Mapped[Optional[str]] = mapped_column(Text)
    document_type: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[DocumentStatus]] = mapped_column(
        ENUM(DocumentStatus), nullable=True
    )
    entry_date: Mapped[datetime.date] = mapped_column(
        Date, default=datetime.datetime.today
    )

    def get_document_type(self):
        doc_type = LocalPlanDocumentType.query.filter(
            LocalPlanDocumentType.name == self.document_type
        ).one_or_none()
        return doc_type


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


class EventCategory(Enum):
    ESTIMATED_REGULATION_18 = "Estimated regulation 18"
    ESTIMATED_REGULATION_19 = "Estimated regulation 19"
    ESTIMATED_EXAMINATION_AND_ADOPTION = "Estimated examination and adoption"
    REGULATION_18 = "Regulation 18"
    REGULATION_19 = "Regulation 19"
    EXAMINATION_AND_ADOPTION = "Examination and adoption"

    def stage(self):
        if "REGULATION" in self.name:
            return re.search(r"\d+", self.name).group()
        return None

    def prefix(self):
        if "ESTIMATED" in self.name:
            return "estimated"
        return ""


class LocalPlanEventType(BaseModel):
    __tablename__ = "local_plan_event_type"


class LocalPlanEvent(BaseModel):
    __tablename__ = "local_plan_event"

    event_category: Mapped[EventCategory] = mapped_column(ENUM(EventCategory))

    event_data: Mapped[Optional[dict]] = mapped_column(MutableDict.as_mutable(JSONB))

    created_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )
    local_plan_timetable: Mapped[str] = mapped_column(
        ForeignKey("local_plan_timetable.reference")
    )
    timetable: Mapped["LocalPlanTimetable"] = relationship(back_populates="events")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # TODO not sure this is correct at the moment - need to check
    def event_status(self):
        for key, value in self.event_data.items():
            if key == "notes":
                continue
            if all(value.get(k, "").strip() != "" for k in ["day", "month", "year"]):
                return "completed"
        return "started"

    def plan_published(self):
        prefix = (
            "estimated_" if "estimated" in self.event_category.value.lower() else ""
        )
        match self.event_category:
            case EventCategory.ESTIMATED_REGULATION_18 | EventCategory.REGULATION_18:
                return self.collect_date_fields(
                    f"{prefix}reg_18_draft_local_plan_published"
                )
            case EventCategory.ESTIMATED_REGULATION_19 | EventCategory.REGULATION_19:
                return self.collect_date_fields(
                    f"{prefix}reg_19_publication_local_plan_published"
                )
            case _:
                return None

    def plan_published_text(self):
        stage = self.event_category.stage()
        if stage == "18":
            plan_published_text = "Draft local plan published"
        elif stage == "19":
            plan_published_text = "Publication local plan published"
        else:
            plan_published_text = None
        return plan_published_text

    def consultation_start(self):
        prefix = (
            "estimated_" if "estimated" in self.event_category.value.lower() else ""
        )
        stage = self.event_category.stage()
        match self.event_category:
            case (
                EventCategory.ESTIMATED_REGULATION_18
                | EventCategory.REGULATION_18
                | EventCategory.ESTIMATED_REGULATION_19
                | EventCategory.REGULATION_19
            ):
                return self.collect_date_fields(
                    f"{prefix}reg_{stage}_public_consultation_start"
                )
            case _:
                return None

    def consultation_end(self):
        prefix = (
            "estimated_" if "estimated" in self.event_category.value.lower() else ""
        )
        stage = self.event_category.stage()
        match self.event_category:
            case (
                EventCategory.ESTIMATED_REGULATION_18
                | EventCategory.REGULATION_18
                | EventCategory.ESTIMATED_REGULATION_19
                | EventCategory.REGULATION_19
            ):
                return self.collect_date_fields(
                    f"{prefix}reg_{stage}_public_consultation_end"
                )
            case _:
                return None

    def submit_plan_for_examination(self):
        prefix = (
            "estimated_" if "estimated" in self.event_category.value.lower() else ""
        )
        return self.collect_date_fields(f"{prefix}submit_plan_for_examination")

    def plan_adoption_date(self):
        prefix = (
            "estimated_" if "estimated" in self.event_category.value.lower() else ""
        )
        return self.collect_date_fields(f"{prefix}plan_adoption_date")

    def collect_date_fields(self, key):
        dates = self.event_data.get(key, None)
        if dates is None:
            return None
        date_parts = []
        if dates.get("day", None):
            date_parts.append(dates["day"])
        if dates.get("month", None):
            date_parts.append(dates["month"])
        if dates.get("year", None):
            date_parts.append(dates["year"])
        return "/".join(date_parts)

    def get_event_type_name(self, key):
        if key not in self.event_data:
            return ""
        event_type_refererence = key.replace("_", "-")
        event_type = LocalPlanEventType.query.get(event_type_refererence)
        if event_type is None:
            return ""
        return event_type.name

    def ordered_event_data(self):
        if self.event_category in [EventCategory.EXAMINATION_AND_ADOPTION]:
            ordered = OrderedDict()
            if "submit_plan_for_examination" in self.event_data:
                ordered["submit_plan_for_examination"] = self.event_data[
                    "submit_plan_for_examination"
                ]
                ordered["planning_inspectorate_examination_start"] = self.event_data[
                    "planning_inspectorate_examination_start"
                ]
                ordered["planning_inspectorate_examination_end"] = self.event_data[
                    "planning_inspectorate_examination_end"
                ]

            if "planning_inspectorate_found_sound" in self.event_data:
                ordered["planning_inspectorate_found_sound"] = self.event_data[
                    "planning_inspectorate_found_sound"
                ]
                ordered["inspector_report_published"] = self.event_data[
                    "inspector_report_published"
                ]
                ordered["plan_adopted"] = self.event_data["plan_adopted"]
            return ordered
        return self.event_data


class LocalPlanTimetable(DateModel):
    __tablename__ = "local_plan_timetable"

    reference: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    local_plan: Mapped[str] = mapped_column(ForeignKey("local_plan.reference"))
    local_plan_obj: Mapped["LocalPlan"] = relationship(back_populates="timetable")
    events: Mapped[List["LocalPlanEvent"]] = relationship(lazy="joined")

    def event_category_progress(self, event_category):
        events = [
            event for event in self.events if event.event_category == event_category
        ]
        if not events:
            return "not started"
        if all(event.event_status() == "completed" for event in events):
            return "completed"
        if any(event.event_status() == "started" for event in events):
            return "started"

    def get_events_by_category(self, category):
        return [event for event in self.events if event.event_category == category]
