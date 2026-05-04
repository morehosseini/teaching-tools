"""
Pydantic data models for the Construction Planning Agent.

Implements the activity data structure from §18 of the final plan, with three-point
durations, AACE class labels, audit fields, and nullable BIM/cost stubs.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class ProjectType(str, Enum):
    DETACHED_HOUSE = "detached_house"
    TOWNHOUSE = "townhouse"
    MEDIUM_DENSITY = "medium_density"
    HIGH_RISE_RESIDENTIAL = "high_rise_residential"
    SMALL_COMMERCIAL = "small_commercial"
    HIGH_RISE_COMMERCIAL = "high_rise_commercial"
    WAREHOUSE = "warehouse"
    SCHOOL_EXTENSION = "school_extension"
    FITOUT = "fitout"
    REFURBISHMENT = "refurbishment"
    COMMUNITY_FACILITY = "community_facility"


class ActivityType(str, Enum):
    DESIGN = "design"
    APPROVAL = "approval"
    PROCUREMENT = "procurement"
    CONSTRUCTION = "construction"
    INSPECTION = "inspection"
    COMMISSIONING = "commissioning"
    HANDOVER = "handover"
    MILESTONE = "milestone"
    PRELIMINARY = "preliminary"


class RelationshipType(str, Enum):
    FS = "FS"  # Finish-to-Start
    SS = "SS"  # Start-to-Start
    FF = "FF"  # Finish-to-Finish
    SF = "SF"  # Start-to-Finish


class AACEClass(str, Enum):
    CLASS_5 = "Class 5"  # Concept screening: -50%/+100%
    CLASS_4 = "Class 4"  # Feasibility: -30%/+50%
    CLASS_3 = "Class 3"  # Budget authorisation: -20%/+30%
    CLASS_2 = "Class 2"  # Control baseline: -15%/+20%
    CLASS_1 = "Class 1"  # Bid/definitive: -10%/+15%


class Severity(str, Enum):
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"


class UnknownHandling(str, Enum):
    CONSERVATIVE = "unknown_conservative"
    HIGH_RISK = "unknown_high_risk"


class PIRStatus(str, Enum):
    USER_PROVIDED = "user_provided"
    DEFAULT_APPLIED = "default_applied"
    UNKNOWN_CONSERVATIVE = "unknown_conservative"
    UNKNOWN_HIGH_RISK = "unknown_high_risk"
    LLM_INFERRED = "llm_inferred"


class QuantitySource(str, Enum):
    USER_INPUT = "user_input"
    TYPOLOGICAL_INFERENCE = "typological_inference"
    LIBRARY_LOOKUP = "library_lookup"
    LLM_INFERENCE = "llm_inference"


class RateSource(str, Enum):
    LIBRARY = "library"
    LLM_INFERENCE = "llm_inference_flagged"
    USER_OVERRIDE = "user_override"


# ── Supporting Models ──────────────────────────────────────────────────────────

class Predecessor(BaseModel):
    """A dependency relationship to another activity."""
    activity_id: str
    relationship_type: RelationshipType = RelationshipType.FS
    lag_days: int = 0
    lag_reason: Optional[str] = None


class AuditEntry(BaseModel):
    """Tracks who created/edited an item and when."""
    generated_by: str = "agent_v1.0"
    generated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    edited_by: Optional[str] = None
    edited_at: Optional[datetime.datetime] = None
    edit_reason: Optional[str] = None


class PIRVariable(BaseModel):
    """A single Project Information Request variable with its value and metadata."""
    name: str
    label: str
    value: Optional[Union[str, int, float, bool]] = None
    status: PIRStatus = PIRStatus.DEFAULT_APPLIED
    default_value: Optional[Union[str, int, float, bool]] = None
    default_rationale: Optional[str] = None
    schedule_impact: Optional[str] = None
    source: Optional[str] = None
    options: Optional[list[str]] = None
    input_type: str = "text"  # text, number, select, radio, checkbox


class ValidationResult(BaseModel):
    """A single validation finding."""
    rule_id: str
    description: str
    severity: Severity
    affected_activities: list[str] = Field(default_factory=list)
    suggested_fix: Optional[str] = None
    source: Optional[str] = None
    overridden: bool = False
    override_reason: Optional[str] = None


# ── WBS ────────────────────────────────────────────────────────────────────────

class WBSElement(BaseModel):
    """A Work Breakdown Structure element (deliverable-based)."""
    wbs_code: str  # e.g. "7.2.1"
    parent_code: Optional[str] = None  # e.g. "7.2"
    name: str  # e.g. "Ground Floor Slab"
    level: int  # 1-4
    description: Optional[str] = None
    inclusions: Optional[list[str]] = None
    exclusions: Optional[list[str]] = None
    deliverables: Optional[list[str]] = None
    confidence_level: AACEClass = AACEClass.CLASS_5


# ── Activity ───────────────────────────────────────────────────────────────────

class Activity(BaseModel):
    """
    Full activity data structure per §18 of the final plan.
    Nullable fields are stubbed for future phases (BIM, cost, resources).
    """
    # Identity
    activity_id: str  # e.g. "A120"
    wbs_code: str  # e.g. "7.2.1"
    wbs_name: str  # e.g. "Substructure / Ground Floor / Concrete"
    activity_name: str  # e.g. "Construct ground floor slab"
    activity_type: ActivityType = ActivityType.CONSTRUCTION

    # Location and spatial (nullable for future BIM)
    location_zone: Optional[str] = None
    spatial_guid: Optional[str] = None
    ifc_element_id: Optional[str] = None

    # Trade and responsibility
    trade: Optional[str] = None
    responsible_party: Optional[str] = "Head Contractor"

    # Quantity and production
    quantity: Optional[float] = None
    unit: Optional[str] = None
    quantity_source: Optional[str] = None
    production_rate: Optional[float] = None
    production_rate_unit: Optional[str] = None
    production_rate_low: Optional[float] = None
    production_rate_high: Optional[float] = None
    production_rate_source: Optional[str] = None
    crew_composition: Optional[str] = None

    # Three-point durations (always carried from day one per §8.2)
    duration_optimistic_days: Optional[int] = None
    duration_most_likely_days: int = 1
    duration_pessimistic_days: Optional[int] = None

    # Calendar
    calendar_id: str = "VIC_5DAY_STANDARD_2026"
    calendar_efficiency_factor: float = 1.0

    # Dependencies
    predecessors: list[Predecessor] = Field(default_factory=list)
    successors: list[Predecessor] = Field(default_factory=list)

    # Constraints and inspections
    permit_required: bool = False
    inspection_hold: bool = False
    inspection_milestone_id: Optional[str] = None
    weather_sensitive: bool = False

    # Procurement linkage
    procurement_item: bool = False
    procurement_chain_ref: Optional[str] = None
    lead_time_weeks: Optional[int] = None

    # Risk and confidence
    buffer_days: int = 0
    risk_weighting: str = "Medium"
    confidence_level: AACEClass = AACEClass.CLASS_5
    human_review_required: bool = True
    assumption: Optional[str] = None

    # Cost (nullable, stubbed for Phase 3 per §18)
    budgeted_cost: Optional[float] = None
    cost_loading_rule: Optional[str] = None

    # CPM results (populated by cpm_engine, not by LLM)
    early_start: Optional[datetime.date] = None
    early_finish: Optional[datetime.date] = None
    late_start: Optional[datetime.date] = None
    late_finish: Optional[datetime.date] = None
    total_float: Optional[int] = None
    free_float: Optional[int] = None
    is_critical: bool = False

    # Audit
    audit: AuditEntry = Field(default_factory=AuditEntry)


# ── Procurement Item ───────────────────────────────────────────────────────────

class ProcurementItem(BaseModel):
    """A long-lead procurement item with full chain per §10.2."""
    item_id: str  # e.g. "PROC-001"
    item_category: str  # e.g. "switchboard_commercial_400A"
    description: str
    installation_activity_id: Optional[str] = None  # linked activity in schedule

    # Chain durations (working days)
    design_freeze_days: int = 5
    shop_drawing_days: int = 10
    consultant_review_days: int = 10
    approval_days: int = 5
    sample_approval_days: Optional[int] = None
    fabrication_days: int = 20
    delivery_days: int = 5

    # Total lead time
    total_lead_weeks_min: Optional[int] = None
    total_lead_weeks_max: Optional[int] = None

    # Metadata
    source: Optional[str] = None
    notes: Optional[str] = None
    audit: AuditEntry = Field(default_factory=AuditEntry)


# ── Risk Register Entry ────────────────────────────────────────────────────────

class RiskEntry(BaseModel):
    """A risk or assumption entry linked to activities."""
    risk_id: str
    description: str
    category: str = "Schedule"
    likelihood: str = "Medium"
    impact: str = "Medium"
    linked_activities: list[str] = Field(default_factory=list)
    mitigation: Optional[str] = None
    owner: Optional[str] = None
    status: str = "Open"


# ── Planning Basis ─────────────────────────────────────────────────────────────

class PlanningBasis(BaseModel):
    """The Planning Basis Summary — the agent's handshake with the user (§4.5)."""
    project_type: ProjectType
    project_description: str
    location: Optional[str] = None
    gfa_m2: Optional[float] = None
    storeys: Optional[int] = None
    structural_system: Optional[str] = None
    soil_class: Optional[str] = None
    calendar_id: str = "VIC_5DAY_STANDARD_2026"
    aace_class: AACEClass = AACEClass.CLASS_5

    pir_variables: list[PIRVariable] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    risks_flagged: list[str] = Field(default_factory=list)

    approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[datetime.datetime] = None


# ── Project (top-level container) ──────────────────────────────────────────────

class Project(BaseModel):
    """Top-level project container holding all planning data."""
    project_id: str = "PROJ-001"
    project_name: str = "Untitled Project"
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)

    # Planning basis
    planning_basis: Optional[PlanningBasis] = None

    # Schedule components
    wbs_elements: list[WBSElement] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
    procurement_items: list[ProcurementItem] = Field(default_factory=list)
    risks: list[RiskEntry] = Field(default_factory=list)

    # Validation
    validation_results: list[ValidationResult] = Field(default_factory=list)

    # Schedule metadata
    project_start_date: datetime.date = Field(
        default_factory=lambda: datetime.date(2026, 7, 1)
    )
    p50_completion: Optional[datetime.date] = None
    p80_completion: Optional[datetime.date] = None

    # State
    schedule_version: str = "Target"
    basis_of_schedule_narrative: Optional[str] = None
    critical_path_narrative: Optional[str] = None
    disclaimer: str = (
        "This schedule is a preliminary planning output (AACE Class 5 or Class 4) "
        "generated from limited project information. Durations, sequencing, procurement "
        "assumptions, resources, calendars, and risks are indicative only. The output is "
        "not contractually reliable and must not be appended to tender documents, contracts, "
        "or site-execution instructions without review, correction, and approval by an "
        "appropriately qualified and insured construction planner, project manager, or "
        "superintendent. Quantities marked as parametric or typologically inferred require "
        "independent verification before any cost or duration commitment."
    )
