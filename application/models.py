import datetime
import re
from enum import Enum
from typing import List, Optional, Union

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

    @property
    def adopted_date(self):
        for event in self.timetable.events:
            if event.event_type.reference == "plan-adopted":
                return event.event_date
        return ""

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

    timetable: Mapped[Optional["LocalPlanTimetable"]] = relationship(
        back_populates="local_plan_obj", uselist=False
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


class LocalPlanEvent(BaseModel):
    __tablename__ = "local_plan_event"

    event_category: Mapped[EventCategory] = mapped_column(ENUM(EventCategory))

    event_data: Mapped[Optional[dict]] = mapped_column(MutableDict.as_mutable(JSONB))
    event_date: Mapped[Optional[str]] = mapped_column(Text)
    event_type: Mapped[Optional["LocalPlanEventType"]] = relationship()
    local_plan_event: Mapped[Optional[str]] = mapped_column(
        ForeignKey("local_plan_event_type.reference")
    )

    created_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now
    )
    local_plan_timetable: Mapped[str] = mapped_column(
        ForeignKey("local_plan_timetable.reference")
    )
    timetable: Mapped["LocalPlanTimetable"] = relationship(back_populates="events")
    notes: Mapped[Optional[str]] = mapped_column(Text)

    @property
    def local_plan(self):
        return self.timetable.local_plan

    @property
    def organisations(self):
        return self.timetable.local_plan_obj.organisations

    def collect_date_fields(self, key):
        try:
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
        except Exception as e:
            print(f"Error collecting date fields for key {key}: {e}")
            return None

    def collect_iso_date_fields(self, key):
        try:
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
        except Exception as e:
            print(f"Error collecting ISO date fields for key {key}: {e}")
            return None

    def get_event_type_name(self, key):
        if key not in self.event_data:
            return ""
        event_type_refererence = key.replace("_", "-")
        event_type = LocalPlanEventType.query.get(event_type_refererence)
        if event_type is None:
            return ""
        return event_type.name


class LocalPlanTimetable(DateModel):
    __tablename__ = "local_plan_timetable"

    reference: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    local_plan: Mapped[str] = mapped_column(ForeignKey("local_plan.reference"))
    local_plan_obj: Mapped["LocalPlan"] = relationship(back_populates="timetable")
    events: Mapped[List["LocalPlanEvent"]] = relationship(lazy="joined")

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
            for event in self.events
            if event.event_date is not None and event.end_date is None
        ]

        # Sort by parsed date
        dated_events.sort(key=lambda x: x[1], reverse=reverse)

        # Return just the event objects
        return [event for event, _ in dated_events]

    def timeline(self):
        entries = []

        # # Check for Draft local plan published event
        # draft_plan_entry = None
        # has_draft_plan = False

        # for event in self.get_actual_events():
        #     # Check each event's entries for draft plan published
        #     event_entries = event.as_timeline_entry()
        #     for entry in event_entries:
        #         if entry.name == "Draft local plan published":
        #             draft_plan_entry = entry
        #             has_draft_plan = True
        #         else:
        #             entries.append(entry)

        # # If no draft plan entry found, create one with no date
        # if not has_draft_plan:
        #     draft_plan_entry = TimelineEntry(
        #         name="Draft local plan published",
        #         start_date=None,
        #         end_date=None,
        #         notes="",
        #     )

        # # Sort the main entries
        # entries.sort()

        # # Add adopted date if it exists
        # if self.local_plan_obj.adopted_date:
        #     adopted_date = TimelineEntry(
        #         name="Plan adopted",
        #         start_date=self.local_plan_obj.adopted_date,
        #         end_date=None,
        #         notes="",
        #     )
        # else:
        #     adopted_date = TimelineEntry(
        #         name="Plan adopted",
        #         start_date=None,
        #         end_date=None,
        #         notes="",
        #     )
        #     entries = [adopted_date] + entries

        # # Always put draft at the end so it renders as the first event
        # # as timeline reads from top to bottom - oldest first latest last
        # entries = entries + [draft_plan_entry]

        return entries


class TimelineEntry:
    def __init__(
        self,
        *,  # Force keyword arguments
        name: str,
        start_date: Union[datetime.datetime, str, None],
        end_date: Union[datetime.datetime, str, None] = None,
        notes: str = "",
    ):
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.notes = notes

    def _parse_date(self, date_str):
        """Helper method to parse dates in formats: dd/mm/yyyy, mm/yyyy, or yyyy"""
        try:
            # Try dd/mm/yyyy
            if date_str.count("/") == 2:
                return datetime.datetime.strptime(date_str, "%d/%m/%Y")

            # Try mm/yyyy
            elif date_str.count("/") == 1:
                # For mm/yyyy, set to first of month
                dt = datetime.datetime.strptime(date_str, "%m/%Y")
                return dt.replace(day=1)

            # Try yyyy
            else:
                # For yyyy, set to January 1st
                return datetime.datetime.strptime(f"01/01/{date_str}", "%d/%m/%Y")

        except ValueError as e:
            print(f"Failed to parse date: {date_str}, error: {e}")
            return None

    def date(self):
        if self.start_date and self.end_date:
            return f"{self.start_date} to {self.end_date}"
        elif self.start_date:
            return self.start_date
        else:
            return "Date unavailable"

    def __lt__(self, other):
        if not isinstance(other, TimelineEntry):
            return NotImplemented

        # Plan adopted always goes last
        if self.name == "Plan adopted":
            return False
        if other.name == "Plan adopted":
            return True

        # Parse dates first
        self_date = self._parse_date(self.start_date)
        other_date = self._parse_date(other.start_date)

        # Handle cases where dates might be None
        if self_date is None and other_date is None:
            return False
        if self_date is None:
            return True  # None dates go at the end
        if other_date is None:
            return False

        # For same dates, use chronological order
        return self_date > other_date  # Changed to reverse chronological

    def __eq__(self, other):
        if not isinstance(other, TimelineEntry):
            return NotImplemented
        return self.start_date == other.start_date and self.name == other.name

    def to_dict(self):
        return {"name": self.name, "date": self.date(), "notes": self.notes}
