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
    lds_published_date: Mapped[Optional[str]] = mapped_column(Text)

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
    TIMETABLE_PUBLISHED = "Timetable published"
    ESTIMATED_REGULATION_18 = "Estimated regulation 18"
    ESTIMATED_REGULATION_19 = "Estimated regulation 19"
    ESTIMATED_EXAMINATION_AND_ADOPTION = "Estimated examination and adoption"
    REGULATION_18 = "Regulation 18"
    REGULATION_19 = "Regulation 19"
    PLANNING_INSPECTORATE_EXAMINATION = "Planning inspectorate examination"
    PLANNING_INSPECTORATE_FINDINGS = "Planning inspectorate findings"

    def stage(self):
        if "REGULATION" in self.name:
            return re.search(r"\d+", self.name).group()
        return None

    def prefix(self):
        if "ESTIMATED" in self.name:
            return "estimated"
        return ""

    def actual_dates_category(self):
        if "ESTIMATED" in self.name or "TIMETABLE" in self.name:
            return False
        return True

    def timeline_name(self):
        match self:
            case EventCategory.TIMETABLE_PUBLISHED:
                return "Timetable published"
            case EventCategory.REGULATION_18 | EventCategory.REGULATION_19:
                return f"{self.value} consultation"
            case EventCategory.PLANNING_INSPECTORATE_EXAMINATION:
                return f"{self.value} period"
            case EventCategory.PLANNING_INSPECTORATE_FINDINGS:
                return "Planning inspectorate findings"
            case _:
                return self.name

    def ordered_event_types(self):
        match self:
            # case EventCategory.TIMETABLE_PUBLISHED:
            #     return ["timetable_published"]
            case EventCategory.ESTIMATED_REGULATION_18:
                return [
                    "estimated_reg_18_draft_local_plan_published",
                    "estimated_reg_18_public_consultation_start",
                    "estimated_reg_18_public_consultation_end",
                ]
            case EventCategory.ESTIMATED_REGULATION_19:
                return [
                    "estimated_reg_19_publication_local_plan_published",
                    "estimated_reg_19_public_consultation_start",
                    "estimated_reg_19_public_consultation_end",
                ]
            case EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION:
                return [
                    "estimated_submit_plan_for_examination",
                    "estimated_plan_adoption_date",
                ]
            case EventCategory.REGULATION_18:
                return [
                    "reg_18_draft_local_plan_published",
                    "reg_18_public_consultation_start",
                    "reg_18_public_consultation_end",
                ]
            case EventCategory.REGULATION_19:
                return [
                    "reg_19_publication_local_plan_published",
                    "reg_19_public_consultation_start",
                    "reg_19_public_consultation_end",
                ]
            case EventCategory.PLANNING_INSPECTORATE_EXAMINATION:
                return [
                    "planning_inspectorate_examination_start",
                    "planning_inspectorate_examination_end",
                ]
            case EventCategory.PLANNING_INSPECTORATE_FINDINGS:
                return [
                    "planning_inspectorate_found_sound",
                    "inspector_report_published",
                ]
            case _:
                return []


class LocalPlanEventType(BaseModel):
    __tablename__ = "local_plan_event_type"

    event_category: Mapped[Optional[EventCategory]] = mapped_column(ENUM(EventCategory))


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

    def event_status(self):
        for key, value in self.event_data.items():
            if key == "notes" or key == "csrf_token":
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

    def collect_iso_date_fields(self, key):
        dates = self.event_data.get(key, None)
        if dates is None:
            return None
        date_parts = []
        if dates.get("year", None):
            date_parts.append(dates["year"])
        if dates.get("month", None):
            date_parts.append(dates["month"])
        if dates.get("day", None):
            date_parts.append(dates["day"])
        return "-".join(date_parts)

    def get_event_type_name(self, key):
        if key not in self.event_data:
            return ""
        event_type_refererence = key.replace("_", "-")
        event_type = LocalPlanEventType.query.get(event_type_refererence)
        if event_type is None:
            return ""
        return event_type.name

    def ordered_event_data(self):
        if self.event_category in [EventCategory.PLANNING_INSPECTORATE_EXAMINATION]:
            ordered = OrderedDict()
            ordered["submit_plan_for_examination"] = self.event_data.get(
                "submit_plan_for_examination"
            )
            ordered["planning_inspectorate_examination_start"] = self.event_data.get(
                "planning_inspectorate_examination_start"
            )
            ordered["planning_inspectorate_examination_end"] = self.event_data.get(
                "planning_inspectorate_examination_end"
            )
            return ordered
        if self.event_category in [EventCategory.PLANNING_INSPECTORATE_FINDINGS]:
            ordered = OrderedDict()
            ordered["planning_inspectorate_found_sound"] = self.event_data.get(
                "planning_inspectorate_found_sound"
            )
            ordered["inspector_report_published"] = self.event_data.get(
                "inspector_report_published"
            )
            ordered["inspector_report_published"] = self.event_data.get(
                "inspector_report_published"
            )
            return ordered
        elif self.event_category in [EventCategory.ESTIMATED_EXAMINATION_AND_ADOPTION]:
            ordered = OrderedDict()
            ordered["estimated_submit_plan_for_examination"] = self.event_data.get(
                "estimated_submit_plan_for_examination"
            )
            ordered["estimated_plan_adoption_date"] = self.event_data.get(
                "estimated_plan_adoption_date"
            )
            return ordered
        elif self.event_category in [
            EventCategory.ESTIMATED_REGULATION_18,
            EventCategory.REGULATION_18,
        ]:
            prefix = (
                "estimated_" if "estimated" in self.event_category.value.lower() else ""
            )
            ordered = OrderedDict()
            ordered[f"{prefix}reg_18_draft_local_plan_published"] = self.event_data.get(
                f"{prefix}reg_18_draft_local_plan_published"
            )
            ordered[f"{prefix}reg_18_public_consultation_start"] = self.event_data.get(
                f"{prefix}reg_18_public_consultation_start"
            )
            ordered[f"{prefix}reg_18_public_consultation_end"] = self.event_data.get(
                f"{prefix}reg_18_public_consultation_end"
            )
            return ordered
        elif self.event_category in [
            EventCategory.ESTIMATED_REGULATION_19,
            EventCategory.REGULATION_19,
        ]:
            prefix = (
                "estimated_" if "estimated" in self.event_category.value.lower() else ""
            )
            ordered = OrderedDict()
            ordered[
                f"{prefix}reg_19_publication_local_plan_published"
            ] = self.event_data.get(f"{prefix}reg_19_publication_local_plan_published")
            ordered[f"{prefix}reg_19_public_consultation_start"] = self.event_data.get(
                f"{prefix}reg_19_public_consultation_start"
            )
            ordered[f"{prefix}reg_19_public_consultation_end"] = self.event_data.get(
                f"{prefix}reg_19_public_consultation_end"
            )
            return ordered
        return self.event_data

    def is_first_event_of_category(self):
        earlier_events = self.query.filter(
            LocalPlanEvent.timetable == self.timetable,
            LocalPlanEvent.event_category == self.event_category,
            LocalPlanEvent.created_date < self.created_date,
        ).all()
        return True if not earlier_events else False

    def as_timeline_entry(self):
        match self.event_category:
            case EventCategory.TIMETABLE_PUBLISHED:
                data = []
                data.append(
                    {
                        "name": "Timetable published",
                        "date": self.collect_date_fields("timetable_published"),
                        "notes": self.notes if self.notes else "",
                    }
                )
                return data
            case EventCategory.REGULATION_18:
                data = []
                if (
                    "reg_18_draft_local_plan_published" in self.event_data
                    and self.is_first_event_of_category()
                ):
                    date = self.collect_date_fields("reg_18_draft_local_plan_published")
                    data.append(
                        {
                            "name": "Draft local plan published",
                            "date": "Date unavailable",
                        }
                    )
                start_date = self.collect_date_fields(
                    "reg_18_public_consultation_start"
                )
                end_date = self.collect_date_fields("reg_18_public_consultation_end")

                if start_date and end_date:
                    consultation_text = f"{start_date} to {end_date}"
                elif start_date and not end_date:
                    consultation_text = f"{start_date} to date unavailable"
                elif not start_date and end_date:
                    consultation_text = f"Date unavailable to {end_date}"
                else:
                    consultation_text = "Date unavailable"

                data.append(
                    {
                        "name": "Regulation 18 consultation",
                        "date": consultation_text,
                        "notes": self.notes if self.notes else "",
                    }
                )
                return data
            case EventCategory.REGULATION_19:
                data = []
                if (
                    "reg_19_publication_local_plan_published" in self.event_data
                    and self.is_first_event_of_category()
                ):
                    date = self.collect_date_fields(
                        "reg_19_publication_local_plan_published"
                    )
                    data.append(
                        {
                            "name": "Publication local plan published",
                            "date": date if date else "Date unavailable",
                        }
                    )
                start_date = self.collect_date_fields(
                    "reg_19_public_consultation_start"
                )
                end_date = self.collect_date_fields("reg_19_public_consultation_end")

                if start_date and end_date:
                    consultation_text = f"{start_date} to {end_date}"
                elif start_date and not end_date:
                    consultation_text = f"{start_date} to date unavailable"
                elif not start_date and end_date:
                    consultation_text = f"Date unavailable to {end_date}"
                else:
                    consultation_text = "Date unavailable"

                data.append(
                    {
                        "name": "Regulation 19 consultation",
                        "date": consultation_text,
                        "notes": self.notes if self.notes else "",
                    }
                )
                return data

            case EventCategory.PLANNING_INSPECTORATE_EXAMINATION:
                data = []
                data.append(
                    {
                        "name": "Submit plan for examination",
                        "date": self.collect_date_fields("submit_plan_for_examination"),
                        "notes": self.notes if self.notes else "",
                    }
                )
                start_date = self.collect_date_fields(
                    "planning_inspectorate_examination_start"
                )
                end_date = self.collect_date_fields(
                    "planning_inspectorate_examination_end"
                )
                data.append(
                    {
                        "name": "Planning inspectorate examination period",
                        "date": f"{start_date} to {end_date}",
                        "notes": self.notes if self.notes else "",
                    }
                )
                return data
            case EventCategory.PLANNING_INSPECTORATE_FINDINGS:
                data = []
                keys = self.event_category.ordered_event_types()
                for key in keys:
                    event_type = LocalPlanEventType.query.get(key.replace("_", "-"))
                    if event_type:
                        data.append(
                            {
                                "name": event_type.name,
                                "date": self.collect_date_fields(key),
                                "notes": self.notes if self.notes else "",
                            }
                        )
                return data
            case _:
                return []


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

    def get_actual_events(self):
        return [
            event
            for event in self.events
            if event.event_category
            in [
                EventCategory.TIMETABLE_PUBLISHED,
                EventCategory.REGULATION_18,
                EventCategory.REGULATION_19,
                EventCategory.PLANNING_INSPECTORATE_EXAMINATION,
                EventCategory.PLANNING_INSPECTORATE_FINDINGS,
            ]
        ]

    def has_actual_events(self):
        return len(self.get_actual_events()) > 0

    def timeline(self):
        event_category_order = [
            category for category in EventCategory if category.actual_dates_category()
        ]
        events = []
        first_reg_18 = True
        first_reg_19 = True
        for category in event_category_order:
            events_by_category = self.get_events_by_category(category)
            if not events_by_category:
                if category == EventCategory.REGULATION_18 and first_reg_18:
                    data = {
                        "name": "Draft local plan published",
                        "date": "Date unavailable",
                        "notes": "",
                    }
                    first_reg_18 = False
                elif category == EventCategory.REGULATION_19 and first_reg_19:
                    data = {
                        "name": "Publication local plan published",
                        "date": "Date unavailable",
                        "notes": "",
                    }
                    first_reg_19 = False
                else:
                    data = {
                        "name": category.timeline_name(),
                        "date": "Date unavailable",
                        "notes": "",
                    }
                events.append(data)
            else:
                for event in events_by_category:
                    events.extend(event.as_timeline_entry())

        if self.local_plan_obj.adopted_date:
            adopted_date_text = self.local_plan_obj.adopted_date
            if adopted_date_text.replace("-", "") == "":
                adopted_date_text = "Date unavailable"
            events.append(
                {
                    "name": "Plan adopted",
                    "date": adopted_date_text,
                }
            )
        # reverse the events so the most recent ones are at the top
        return events[::-1]
