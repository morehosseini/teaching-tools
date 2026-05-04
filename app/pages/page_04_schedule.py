"""Page 4: Schedule Generation and Review."""

import streamlit as st
import pandas as pd
import os
import json
import datetime
import re
from core.llm_service import (
    COMMERCIAL_USE_TERMS,
    RESIDENTIAL_USE_TERMS,
    generate_wbs_and_activities,
    generate_basis_of_schedule,
)
from core.calendar_engine import default_calendar_for_location, get_available_calendars, load_calendar_from_library
from core.models import Project, Activity, ActivityType, WBSElement, ProcurementItem, RelationshipType, Predecessor, AACEClass
from core.cpm_engine import run_cpm
from core.validation_engine import validate_project, get_validation_summary

# Get the path to the app directory
APP_DIR = os.path.dirname(os.path.dirname(__file__))


def _format_label(value):
    if value is None:
        return ""
    return str(value).replace("_", " ").title()


def _normalise_enum(value, enum_cls, default):
    if isinstance(value, enum_cls):
        return value
    if value is None:
        return default

    text = str(value).strip()
    for item in enum_cls:
        candidates = {
            item.value.lower(),
            item.name.lower(),
            item.value.lower().replace(" ", "_"),
            item.value.lower().replace("-", "_"),
        }
        if text.lower().replace("-", "_") in candidates:
            return item
    return default


def _to_int(value, default=0, minimum=0):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        number = default
    return max(minimum, number)


def _to_optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_optional_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_float(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "yes", "y", "1"}


def _parse_predecessors(value):
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = [value]

    predecessors = []
    for item in raw_items:
        if isinstance(item, dict):
            rel_type = _normalise_enum(
                item.get("relationship_type") or item.get("type"),
                RelationshipType,
                RelationshipType.FS,
            )
            activity_id = item.get("activity_id") or item.get("id")
            if activity_id:
                predecessors.append(Predecessor(
                    activity_id=str(activity_id),
                    relationship_type=rel_type,
                    lag_days=_to_int(item.get("lag_days"), default=0),
                    lag_reason=item.get("lag_reason"),
                ))
        else:
            predecessors.append(Predecessor(activity_id=str(item)))
    return predecessors


def _sanitize_wbs_elements(raw_data):
    elements = []
    for idx, item in enumerate(raw_data.get("wbs_elements", []) if isinstance(raw_data, dict) else []):
        if not isinstance(item, dict):
            continue
        code = str(item.get("wbs_code") or item.get("code") or idx + 1)
        name = str(item.get("name") or item.get("wbs_name") or f"WBS {code}")
        elements.append(WBSElement(
            wbs_code=code,
            parent_code=item.get("parent_code"),
            name=name,
            level=_to_int(item.get("level"), default=1, minimum=1),
            description=item.get("description"),
            inclusions=item.get("inclusions"),
            exclusions=item.get("exclusions"),
            deliverables=item.get("deliverables"),
            confidence_level=_normalise_enum(
                item.get("confidence_level"),
                AACEClass,
                AACEClass.CLASS_5,
            ),
        ))
    return elements


def _sanitize_activities(raw_data):
    activities = []
    for idx, item in enumerate(raw_data.get("activities", []) if isinstance(raw_data, dict) else []):
        if not isinstance(item, dict):
            continue

        activity_id = str(item.get("activity_id") or item.get("id") or f"A{(idx + 1) * 10:03d}")
        duration = _to_int(item.get("duration_most_likely_days") or item.get("duration_days"), default=1)
        duration_opt = item.get("duration_optimistic_days")
        duration_pess = item.get("duration_pessimistic_days")

        activities.append(Activity(
            activity_id=activity_id,
            wbs_code=str(item.get("wbs_code") or "1"),
            wbs_name=str(item.get("wbs_name") or item.get("wbs") or "General Works"),
            activity_name=str(item.get("activity_name") or item.get("name") or f"Activity {idx + 1}"),
            activity_type=_normalise_enum(item.get("activity_type"), ActivityType, ActivityType.CONSTRUCTION),
            location_zone=item.get("location_zone") or "Project",
            trade=item.get("trade") or "General",
            responsible_party=item.get("responsible_party") or "Head Contractor",
            quantity=_to_optional_float(item.get("quantity")),
            unit=item.get("unit"),
            quantity_source=item.get("quantity_source"),
            production_rate=_to_optional_float(item.get("production_rate")),
            production_rate_unit=item.get("production_rate_unit"),
            production_rate_low=_to_optional_float(item.get("production_rate_low")),
            production_rate_high=_to_optional_float(item.get("production_rate_high")),
            production_rate_source=item.get("production_rate_source") or "planner_review_required",
            crew_composition=item.get("crew_composition"),
            duration_optimistic_days=_to_int(duration_opt, default=max(0, duration - 1)) if duration_opt is not None else max(0, duration - 1),
            duration_most_likely_days=duration,
            duration_pessimistic_days=_to_int(duration_pess, default=duration + 2) if duration_pess is not None else duration + 2,
            calendar_id=item.get("calendar_id") or "VIC_5DAY_STANDARD_2026",
            calendar_efficiency_factor=_to_float(item.get("calendar_efficiency_factor"), default=1.0),
            predecessors=_parse_predecessors(item.get("predecessors")),
            permit_required=_to_bool(item.get("permit_required")),
            inspection_hold=_to_bool(item.get("inspection_hold")),
            inspection_milestone_id=item.get("inspection_milestone_id"),
            weather_sensitive=_to_bool(item.get("weather_sensitive")),
            procurement_item=_to_bool(item.get("procurement_item")),
            procurement_chain_ref=item.get("procurement_chain_ref"),
            lead_time_weeks=_to_optional_int(item.get("lead_time_weeks")),
            buffer_days=_to_int(item.get("buffer_days"), default=0),
            risk_weighting=item.get("risk_weighting") or "Medium",
            confidence_level=_normalise_enum(item.get("confidence_level"), AACEClass, AACEClass.CLASS_5),
            human_review_required=True if item.get("human_review_required") is None else _to_bool(item.get("human_review_required")),
            assumption=item.get("assumption"),
        ))
    return activities


def _sanitize_procurement_items(raw_data):
    items = []
    for idx, item in enumerate(raw_data.get("procurement_items", []) if isinstance(raw_data, dict) else []):
        if not isinstance(item, dict):
            continue
        description = item.get("description") or item.get("item_category") or f"Procurement item {idx + 1}"
        items.append(ProcurementItem(
            item_id=str(item.get("item_id") or f"P{idx + 1:03d}"),
            item_category=str(item.get("item_category") or "planner_review_required"),
            description=str(description),
            installation_activity_id=item.get("installation_activity_id"),
            design_freeze_days=_to_int(item.get("design_freeze_days"), default=5),
            shop_drawing_days=_to_int(item.get("shop_drawing_days"), default=10),
            consultant_review_days=_to_int(item.get("consultant_review_days"), default=10),
            approval_days=_to_int(item.get("approval_days"), default=5),
            sample_approval_days=_to_optional_int(item.get("sample_approval_days")),
            fabrication_days=_to_int(item.get("fabrication_days"), default=20),
            delivery_days=_to_int(item.get("delivery_days"), default=5),
            total_lead_weeks_min=_to_optional_int(item.get("total_lead_weeks_min")),
            total_lead_weeks_max=_to_optional_int(item.get("total_lead_weeks_max")),
            source=item.get("source"),
            notes=item.get("notes"),
        ))
    return items


def _sort_wbs_code(code):
    parts = []
    for part in str(code).split("."):
        try:
            parts.append((0, int(part)))
        except ValueError:
            parts.append((1, part))
    return parts


def _build_wbs_from_specs(specs, names):
    elements = {}
    for _, wbs_code, wbs_name, *_ in specs:
        parts = str(wbs_code).split(".")
        for depth in range(1, len(parts) + 1):
            code = ".".join(parts[:depth])
            parent = ".".join(parts[:depth - 1]) if depth > 1 else None
            elements[code] = WBSElement(
                wbs_code=code,
                parent_code=parent,
                name=names.get(code) or (wbs_name if code == wbs_code else f"WBS {code}"),
                level=depth,
                description=names.get(f"{code}_description"),
                confidence_level=AACEClass.CLASS_5,
            )
    return [elements[code] for code in sorted(elements, key=_sort_wbs_code)]


def _activities_from_specs(specs):
    return [
        Activity(
            activity_id=activity_id,
            wbs_code=wbs_code,
            wbs_name=wbs_name,
            activity_name=name,
            activity_type=_normalise_enum(activity_type, ActivityType, ActivityType.CONSTRUCTION),
            location_zone="Project",
            trade=trade,
            production_rate_source="template_planner_review_required",
            duration_optimistic_days=max(0, duration - 2),
            duration_most_likely_days=duration,
            duration_pessimistic_days=duration + 4,
            predecessors=[Predecessor(activity_id=pred) for pred in predecessors],
            human_review_required=True,
            assumption="Detailed template activity for planner review and adjustment.",
        )
        for activity_id, wbs_code, wbs_name, name, activity_type, duration, trade, predecessors in specs
    ]


def _split_specs(specs, split_map):
    last_id = {source_id: parts[-1][0] for source_id, parts in split_map.items()}
    part_to_source = {
        part_id: source_id
        for source_id, parts in split_map.items()
        for part_id, _, _ in parts
    }
    expanded = []

    for spec in specs:
        activity_id, wbs_code, wbs_name, name, activity_type, duration, trade, predecessors = spec
        if activity_id not in split_map:
            expanded.append(spec)
            continue

        prior_id = None
        for idx, (part_id, part_name, part_duration) in enumerate(split_map[activity_id]):
            part_predecessors = predecessors if idx == 0 else [prior_id]
            expanded.append((
                part_id,
                wbs_code,
                wbs_name,
                part_name,
                activity_type,
                part_duration,
                trade,
                part_predecessors,
            ))
            prior_id = part_id

    rewired = []
    for spec in expanded:
        activity_id, wbs_code, wbs_name, name, activity_type, duration, trade, predecessors = spec
        source_id = part_to_source.get(activity_id)
        part_ids_for_source = {
            part_id for part_id, _, _ in split_map.get(source_id, [])
        } if source_id else set()
        rewired.append((
            activity_id,
            wbs_code,
            wbs_name,
            name,
            activity_type,
            duration,
            trade,
            [
                pred if pred in part_ids_for_source else last_id.get(pred, pred)
                for pred in predecessors
            ],
        ))
    return rewired


def _fitout_template():
    names = {
        "0": "Pre-Construction",
        "0.1": "Brief, Documentation and Approvals",
        "0.2": "Procurement Planning",
        "1": "Site Establishment and Protection",
        "1.1": "Possession, Protection and Safety",
        "2": "Strip-Out and Demolition",
        "2.1": "Services Isolation and Strip-Out",
        "3": "Partitions and Framing",
        "3.1": "Set-Out, Framing and Openings",
        "4": "Services Rough-In",
        "4.1": "Electrical, Data, Hydraulic, Mechanical and Fire Rough-In",
        "5": "Linings, Ceilings and Wet Areas",
        "5.1": "Insulation, Plasterboard, Stopping and Ceilings",
        "5.2": "Waterproofing and Tiling",
        "6": "Finishes and Fixtures",
        "6.1": "Paint, Floor Finishes, Joinery and Fixtures",
        "7": "Services Fit-Off and Commissioning",
        "7.1": "Fit-Off, Testing and Commissioning",
        "8": "Completion and Handover",
        "8.1": "Cleaning, Defects, Certification and Handover",
    }
    specs = [
        ("A010", "0.1.1", "Brief, Documentation and Approvals", "Confirm tenant brief and scope hold points", "design", 2, "Planner", []),
        ("A020", "0.1.2", "Brief, Documentation and Approvals", "Review fit-out drawings and services design", "design", 4, "Design Team", ["A010"]),
        ("A030", "0.1.3", "Brief, Documentation and Approvals", "Secure landlord and building management approvals", "approval", 5, "Project Manager", ["A020"]),
        ("A040", "0.2.1", "Procurement Planning", "Prepare procurement schedule and samples register", "procurement", 3, "Project Manager", ["A010"]),
        ("A050", "0.2.2", "Procurement Planning", "Release long-lead joinery, glazing and feature finishes", "procurement", 8, "Contractor", ["A040"]),
        ("A060", "1.1.1", "Possession, Protection and Safety", "Take site possession and complete induction", "preliminary", 1, "Builder", ["A030"]),
        ("A070", "1.1.2", "Possession, Protection and Safety", "Record existing condition and dilapidation", "preliminary", 1, "Builder", ["A060"]),
        ("A080", "1.1.3", "Possession, Protection and Safety", "Install temporary protection and site controls", "preliminary", 2, "Builder", ["A060"]),
        ("A090", "2.1.1", "Services Isolation and Strip-Out", "Isolate services and make safe work areas", "construction", 2, "Services", ["A060"]),
        ("A100", "2.1.2", "Services Isolation and Strip-Out", "Demolish redundant partitions and doors", "construction", 4, "Demolition", ["A090"]),
        ("A110", "2.1.3", "Services Isolation and Strip-Out", "Remove redundant ceiling and floor finishes", "construction", 3, "Demolition", ["A090"]),
        ("A120", "2.1.4", "Services Isolation and Strip-Out", "Remove demolition waste and clear work zones", "construction", 2, "Demolition", ["A100", "A110"]),
        ("A130", "3.1.1", "Set-Out, Framing and Openings", "Set out partitions, doors, glazing and services zones", "construction", 2, "Builder", ["A020", "A120"]),
        ("A140", "3.1.2", "Set-Out, Framing and Openings", "Install partition framing and bulkhead framing", "construction", 5, "Carpentry", ["A130"]),
        ("A150", "3.1.3", "Set-Out, Framing and Openings", "Install door frames and backing supports", "construction", 2, "Carpentry", ["A140"]),
        ("A160", "3.1.4", "Set-Out, Framing and Openings", "Install glazed partition frames and channels", "construction", 2, "Glazing", ["A140"]),
        ("A170", "4.1.1", "Electrical, Data, Hydraulic, Mechanical and Fire Rough-In", "Electrical rough-in to walls and ceilings", "construction", 4, "Electrical", ["A140"]),
        ("A180", "4.1.2", "Electrical, Data, Hydraulic, Mechanical and Fire Rough-In", "Data and communications rough-in", "construction", 3, "Data", ["A140"]),
        ("A190", "4.1.3", "Electrical, Data, Hydraulic, Mechanical and Fire Rough-In", "Plumbing rough-in to wet areas and kitchen points", "construction", 3, "Plumbing", ["A140"]),
        ("A200", "4.1.4", "Electrical, Data, Hydraulic, Mechanical and Fire Rough-In", "Mechanical HVAC rough-in and duct alterations", "construction", 4, "Mechanical", ["A140"]),
        ("A210", "4.1.5", "Electrical, Data, Hydraulic, Mechanical and Fire Rough-In", "Fire services rough-in and sprinkler alterations", "construction", 3, "Fire Services", ["A140"]),
        ("A220", "4.1.6", "Electrical, Data, Hydraulic, Mechanical and Fire Rough-In", "Rough-in inspection and close-in approval", "inspection", 1, "Certifier", ["A170", "A180", "A190", "A200", "A210"]),
        ("A230", "5.1.1", "Insulation, Plasterboard, Stopping and Ceilings", "Install acoustic insulation to partitions", "construction", 2, "Insulation", ["A150", "A220"]),
        ("A240", "5.1.2", "Insulation, Plasterboard, Stopping and Ceilings", "Install plasterboard to walls and ceilings", "construction", 5, "Plasterboard", ["A220", "A230"]),
        ("A250", "5.1.3", "Insulation, Plasterboard, Stopping and Ceilings", "Plasterboard stopping and sanding", "construction", 4, "Plasterboard", ["A240"]),
        ("A260", "5.1.4", "Insulation, Plasterboard, Stopping and Ceilings", "Install ceiling grid and access panels", "construction", 3, "Ceilings", ["A220", "A250"]),
        ("A270", "5.2.1", "Waterproofing and Tiling", "Waterproof wet areas", "construction", 2, "Waterproofing", ["A190", "A250"]),
        ("A280", "5.2.2", "Waterproofing and Tiling", "Waterproofing inspection and approval", "inspection", 1, "Certifier", ["A270"]),
        ("A290", "5.2.3", "Waterproofing and Tiling", "Wall and floor tiling to wet areas", "construction", 4, "Tiling", ["A280"]),
        ("A300", "6.1.1", "Paint, Floor Finishes, Joinery and Fixtures", "Apply sealer and paint finishes", "construction", 5, "Painting", ["A250", "A260"]),
        ("A310", "6.1.2", "Paint, Floor Finishes, Joinery and Fixtures", "Prepare floors and complete levelling", "construction", 2, "Flooring", ["A250"]),
        ("A320", "6.1.3", "Paint, Floor Finishes, Joinery and Fixtures", "Install floor finishes", "construction", 4, "Flooring", ["A300", "A310"]),
        ("A330", "6.1.4", "Paint, Floor Finishes, Joinery and Fixtures", "Install joinery, cabinetry and feature items", "construction", 5, "Joinery", ["A050", "A300"]),
        ("A340", "6.1.5", "Paint, Floor Finishes, Joinery and Fixtures", "Install glazed partitions and manifestation", "construction", 3, "Glazing", ["A160", "A300"]),
        ("A350", "6.1.6", "Paint, Floor Finishes, Joinery and Fixtures", "Install internal doors and hardware", "construction", 2, "Carpentry", ["A150", "A300"]),
        ("A360", "6.1.7", "Paint, Floor Finishes, Joinery and Fixtures", "Install fixtures, appliances and loose equipment", "construction", 3, "Builder", ["A290", "A330"]),
        ("A370", "7.1.1", "Fit-Off, Testing and Commissioning", "Electrical fit-off and energisation", "construction", 3, "Electrical", ["A300", "A320"]),
        ("A380", "7.1.2", "Fit-Off, Testing and Commissioning", "Data and AV fit-off", "construction", 2, "Data", ["A300", "A320"]),
        ("A390", "7.1.3", "Fit-Off, Testing and Commissioning", "Plumbing fit-off and fixture connection", "construction", 2, "Plumbing", ["A290", "A360"]),
        ("A400", "7.1.4", "Fit-Off, Testing and Commissioning", "Mechanical fit-off, balancing and controls", "construction", 3, "Mechanical", ["A300", "A320"]),
        ("A410", "7.1.5", "Fit-Off, Testing and Commissioning", "Fire services fit-off and testing", "construction", 2, "Fire Services", ["A300", "A320"]),
        ("A420", "7.1.6", "Fit-Off, Testing and Commissioning", "Integrated services testing and commissioning", "commissioning", 3, "Services", ["A370", "A380", "A390", "A400", "A410"]),
        ("A430", "8.1.1", "Cleaning, Defects, Certification and Handover", "Final clean and presentation clean", "construction", 2, "Cleaner", ["A320", "A330", "A340", "A350", "A360"]),
        ("A440", "8.1.2", "Cleaning, Defects, Certification and Handover", "Defects inspection and punch list", "inspection", 1, "Project Manager", ["A420", "A430"]),
        ("A450", "8.1.3", "Cleaning, Defects, Certification and Handover", "Rectify defects and complete touch-ups", "construction", 3, "Builder", ["A440"]),
        ("A460", "8.1.4", "Cleaning, Defects, Certification and Handover", "Compile certificates, warranties and manuals", "handover", 2, "Project Manager", ["A420"]),
        ("A470", "8.1.5", "Cleaning, Defects, Certification and Handover", "Practical completion and client handover", "handover", 1, "Project Manager", ["A450", "A460"]),
    ]
    return _build_wbs_from_specs(specs, names), _activities_from_specs(specs), []


def _building_template():
    names = {
        "0": "Pre-Construction",
        "0.1": "Design, Approvals and Procurement",
        "1": "Site Works",
        "1.1": "Site Establishment and Earthworks",
        "2": "Substructure",
        "2.1": "Footings, Slab and Under-Slab Services",
        "3": "Superstructure",
        "3.1": "Frame, Upper Floor and Roof Structure",
        "4": "Envelope",
        "4.1": "Roofing, Cladding, Windows and External Doors",
        "5": "Services Rough-In",
        "5.1": "Electrical, Plumbing, HVAC and Data Rough-In",
        "6": "Internal Works and Finishes",
        "6.1": "Linings, Wet Areas, Joinery and Finishes",
        "7": "External Works",
        "7.1": "Drainage, Driveways, Paths and Landscaping",
        "8": "Commissioning and Handover",
        "8.1": "Testing, Defects, Certification and Handover",
    }
    specs = [
        ("A010", "0.1.1", "Design, Approvals and Procurement", "Confirm planning permit and building permit pathway", "approval", 5, "Planner", []),
        ("A020", "0.1.2", "Design, Approvals and Procurement", "Review construction drawings and engineering", "design", 5, "Design Team", ["A010"]),
        ("A030", "0.1.3", "Design, Approvals and Procurement", "Release procurement for windows, structural steel and joinery", "procurement", 5, "Builder", ["A020"]),
        ("A040", "1.1.1", "Site Establishment and Earthworks", "Site possession, fencing and amenities", "preliminary", 3, "Builder", ["A010"]),
        ("A050", "1.1.2", "Site Establishment and Earthworks", "Temporary services and erosion controls", "preliminary", 2, "Builder", ["A040"]),
        ("A060", "1.1.3", "Site Establishment and Earthworks", "Survey set-out and service locating", "construction", 2, "Surveyor", ["A050"]),
        ("A070", "1.1.4", "Site Establishment and Earthworks", "Bulk excavation and spoil removal", "construction", 5, "Earthworks", ["A060"]),
        ("A080", "2.1.1", "Footings, Slab and Under-Slab Services", "Excavate footings and trenches", "construction", 4, "Earthworks", ["A070"]),
        ("A090", "2.1.2", "Footings, Slab and Under-Slab Services", "Install under-slab drainage and plumbing", "construction", 4, "Plumbing", ["A080"]),
        ("A100", "2.1.3", "Footings, Slab and Under-Slab Services", "Place reinforcement and formwork to footings", "construction", 4, "Concrete", ["A090"]),
        ("A110", "2.1.4", "Footings, Slab and Under-Slab Services", "Footing inspection and concrete pour", "inspection", 2, "Concrete", ["A100"]),
        ("A120", "2.1.5", "Footings, Slab and Under-Slab Services", "Prepare slab base, membrane and reinforcement", "construction", 4, "Concrete", ["A110"]),
        ("A130", "2.1.6", "Footings, Slab and Under-Slab Services", "Pour ground floor slab and cure", "construction", 8, "Concrete", ["A120"]),
        ("A140", "3.1.1", "Frame, Upper Floor and Roof Structure", "Set out wall frames and bottom plates", "construction", 2, "Carpentry", ["A130"]),
        ("A150", "3.1.2", "Frame, Upper Floor and Roof Structure", "Erect ground floor wall frame", "construction", 5, "Carpentry", ["A140"]),
        ("A160", "3.1.3", "Frame, Upper Floor and Roof Structure", "Install upper floor structure or ceiling joists", "construction", 5, "Carpentry", ["A150"]),
        ("A170", "3.1.4", "Frame, Upper Floor and Roof Structure", "Erect upper wall frame", "construction", 5, "Carpentry", ["A160"]),
        ("A180", "3.1.5", "Frame, Upper Floor and Roof Structure", "Install roof trusses and bracing", "construction", 5, "Carpentry", ["A170"]),
        ("A190", "3.1.6", "Frame, Upper Floor and Roof Structure", "Frame inspection and close-in approval", "inspection", 1, "Certifier", ["A180"]),
        ("A200", "4.1.1", "Roofing, Cladding, Windows and External Doors", "Install roof covering, flashings and gutters", "construction", 6, "Roofing", ["A180"]),
        ("A210", "4.1.2", "Roofing, Cladding, Windows and External Doors", "Install windows and external doors", "construction", 5, "Glazing", ["A030", "A190"]),
        ("A220", "4.1.3", "Roofing, Cladding, Windows and External Doors", "Install external cladding and weatherproofing", "construction", 7, "Cladding", ["A200", "A210"]),
        ("A230", "5.1.1", "Electrical, Plumbing, HVAC and Data Rough-In", "Electrical rough-in", "construction", 5, "Electrical", ["A190", "A220"]),
        ("A240", "5.1.2", "Electrical, Plumbing, HVAC and Data Rough-In", "Plumbing rough-in", "construction", 5, "Plumbing", ["A190", "A220"]),
        ("A250", "5.1.3", "Electrical, Plumbing, HVAC and Data Rough-In", "HVAC rough-in and ductwork", "construction", 4, "Mechanical", ["A190", "A220"]),
        ("A260", "5.1.4", "Electrical, Plumbing, HVAC and Data Rough-In", "Data and communications rough-in", "construction", 3, "Data", ["A190", "A220"]),
        ("A270", "5.1.5", "Electrical, Plumbing, HVAC and Data Rough-In", "Services rough-in inspection", "inspection", 1, "Certifier", ["A230", "A240", "A250", "A260"]),
        ("A280", "6.1.1", "Linings, Wet Areas, Joinery and Finishes", "Install wall and ceiling insulation", "construction", 3, "Insulation", ["A270"]),
        ("A290", "6.1.2", "Linings, Wet Areas, Joinery and Finishes", "Install plasterboard and internal linings", "construction", 7, "Plasterboard", ["A270", "A280", "A220"]),
        ("A300", "6.1.3", "Linings, Wet Areas, Joinery and Finishes", "Plaster stopping and sanding", "construction", 5, "Plasterboard", ["A290"]),
        ("A310", "6.1.4", "Linings, Wet Areas, Joinery and Finishes", "Waterproof wet areas", "construction", 2, "Waterproofing", ["A240", "A300"]),
        ("A320", "6.1.5", "Linings, Wet Areas, Joinery and Finishes", "Waterproofing inspection", "inspection", 1, "Certifier", ["A310"]),
        ("A330", "6.1.6", "Linings, Wet Areas, Joinery and Finishes", "Tile wet areas", "construction", 5, "Tiling", ["A320"]),
        ("A340", "6.1.7", "Linings, Wet Areas, Joinery and Finishes", "Prime and paint internal surfaces", "construction", 6, "Painting", ["A220", "A300"]),
        ("A350", "6.1.8", "Linings, Wet Areas, Joinery and Finishes", "Install internal doors, architraves and skirtings", "construction", 4, "Carpentry", ["A300"]),
        ("A360", "6.1.9", "Linings, Wet Areas, Joinery and Finishes", "Install joinery and cabinetry", "construction", 5, "Joinery", ["A030", "A340"]),
        ("A370", "6.1.10", "Linings, Wet Areas, Joinery and Finishes", "Install floor finishes", "construction", 5, "Flooring", ["A220", "A340"]),
        ("A380", "6.1.11", "Linings, Wet Areas, Joinery and Finishes", "Fit fixtures, appliances and hardware", "construction", 4, "Builder", ["A330", "A350", "A360", "A370"]),
        ("A390", "7.1.1", "Drainage, Driveways, Paths and Landscaping", "Install external drainage and service connections", "construction", 5, "Civil", ["A220"]),
        ("A400", "7.1.2", "Drainage, Driveways, Paths and Landscaping", "Construct driveway, paths and paving", "construction", 5, "Civil", ["A390"]),
        ("A410", "7.1.3", "Drainage, Driveways, Paths and Landscaping", "Landscaping, fencing and external clean-up", "construction", 5, "Landscaping", ["A400"]),
        ("A420", "8.1.1", "Testing, Defects, Certification and Handover", "Services fit-off and testing", "commissioning", 5, "Services", ["A230", "A240", "A250", "A260", "A340", "A370"]),
        ("A430", "8.1.2", "Testing, Defects, Certification and Handover", "Final building inspection and occupancy certification", "inspection", 2, "Certifier", ["A380", "A410", "A420"]),
        ("A440", "8.1.3", "Testing, Defects, Certification and Handover", "Defects inspection and rectification", "construction", 4, "Builder", ["A430"]),
        ("A450", "8.1.4", "Testing, Defects, Certification and Handover", "Practical completion and handover", "handover", 1, "Project Manager", ["A440"]),
    ]
    return _build_wbs_from_specs(specs, names), _activities_from_specs(specs), []


def _planning_scale(storeys=None, gfa=None):
    basis = st.session_state.get("planning_basis")
    interpretation = st.session_state.get("interpretation") or {}

    storeys = storeys or getattr(basis, "storeys", None) or interpretation.get("storeys") or 18
    gfa = gfa or getattr(basis, "gfa_m2", None) or interpretation.get("gfa_m2") or 14040

    try:
        storeys = int(float(storeys))
    except (TypeError, ValueError):
        storeys = 18

    try:
        gfa = float(str(gfa).replace(",", ""))
    except (TypeError, ValueError):
        gfa = 14040

    return max(10, storeys), gfa


def _highrise_commercial_template(storeys=None, gfa=None):
    storeys, gfa = _planning_scale(storeys, gfa)
    typical_floor_area = max(500, round(gfa / storeys))
    floor_cycle_days = 8

    names = {
        "0": "Pre-Construction, Authorities and Long-Lead Procurement",
        "0.1": "Design, Planning and Permit Basis",
        "0.2": "High-Rise Long-Lead Procurement",
        "1": "CBD Site Establishment and Enabling Works",
        "1.1": "Access, Safety, Services Isolation and Demolition",
        "2": "Substructure and Basement Works",
        "2.1": "Retention, Piling, Excavation and Raft",
        "3": "Superstructure",
        "3.1": "Typical Floor Structure and Core Cycle",
        "4": "Facade and Envelope",
        "4.1": "Facade Installation by Floor Zone",
        "5": "Services Rough-In",
        "5.1": "MEP/F Rough-In by Floor Zone",
        "6": "Internal Fit-Out and Finishes",
        "6.1": "Partitions, Linings, Ceilings and Finishes by Floor Zone",
        "7": "Vertical Transportation and Plant",
        "7.1": "Lifts, Permanent Power and Major Plant",
        "8": "Testing, Commissioning and Handover",
        "8.1": "Integrated Commissioning, Certification and Completion",
    }

    specs = [
        ("H0010", "0.1.1", names["0.1"], "Confirm high-rise scope, staging and planning assumptions", "design", 20, "Planner", []),
        ("H0020", "0.1.2", names["0.1"], "Design development and structural/services coordination", "design", 40, "Design Team", ["H0010"]),
        ("H0030", "0.1.3", names["0.1"], "Town planning and authority consultation period", "approval", 60, "Consultant", ["H0020"]),
        ("H0040", "0.1.4", names["0.1"], "Building permit documentation and approval", "approval", 50, "Consultant", ["H0030"]),
        ("H0050", "0.2.1", names["0.2"], "Tender, subcontractor letting and construction procurement", "procurement", 40, "Builder", ["H0020"]),
        ("H0060", "0.2.2", names["0.2"], "Tower crane, hoist, loading dock and CBD logistics planning", "preliminary", 20, "Builder", ["H0050"]),
        ("H0070", "0.2.3", names["0.2"], "Facade design finalisation, shop drawings and procurement", "procurement", 120, "Facade Contractor", ["H0050"]),
        ("H0080", "0.2.4", names["0.2"], "Lift shop drawings, manufacture and delivery", "procurement", 160, "Lift Contractor", ["H0050"]),
        ("H0090", "0.2.5", names["0.2"], "Mechanical plant procurement and factory testing", "procurement", 120, "Mechanical", ["H0050"]),
        ("H0100", "0.2.6", names["0.2"], "Main switchboards, fire systems and controls procurement", "procurement", 110, "Services", ["H0050"]),
        ("H0110", "1.1.1", names["1.1"], "Site possession, hoarding and CBD pedestrian protection", "preliminary", 10, "Builder", ["H0040", "H0060"]),
        ("H0120", "1.1.2", names["1.1"], "Traffic management, loading dock and crane base establishment", "preliminary", 15, "Builder", ["H0110"]),
        ("H0130", "1.1.3", names["1.1"], "Existing services isolation, diversions and make-safe", "construction", 15, "Services", ["H0110"]),
        ("H0140", "1.1.4", names["1.1"], "Demolition, strip-out and site clearance", "construction", 30, "Demolition", ["H0130"]),
        ("H0150", "2.1.1", names["2.1"], "Retention system, capping beam and monitoring setup", "construction", 35, "Civil", ["H0140"]),
        ("H0160", "2.1.2", names["2.1"], "Bulk excavation and spoil removal", "construction", 45, "Earthworks", ["H0150"]),
        ("H0170", "2.1.3", names["2.1"], "Piling, pile testing and pile trimming", "construction", 40, "Piling", ["H0150"]),
        ("H0180", "2.1.4", names["2.1"], "Pile caps, raft reinforcement and concrete pour", "construction", 35, "Concrete", ["H0160", "H0170"]),
        ("H0190", "2.1.5", names["2.1"], "Basement structure, waterproofing and drainage", "construction", 55, "Concrete", ["H0180"]),
        ("H0200", "2.1.6", names["2.1"], "Ground floor transfer slab and podium structure", "construction", 35, "Concrete", ["H0190"]),
    ]

    previous_structure = "H0200"
    structure_ids = {}
    for floor in range(1, storeys + 1):
        activity_id = f"H{1000 + floor * 10:04d}"
        structure_ids[floor] = activity_id
        specs.append((
            activity_id,
            f"3.1.{floor}",
            names["3.1"],
            f"Level {floor:02d} core, columns and slab cycle ({typical_floor_area} m2 typical floor)",
            "construction",
            floor_cycle_days,
            "Structure",
            [previous_structure],
        ))
        previous_structure = activity_id

    zone_specs = []
    zone_number = 0
    for start_floor in range(1, storeys + 1, 3):
        zone_number += 1
        end_floor = min(storeys, start_floor + 2)
        zone_label = f"Levels {start_floor:02d}-{end_floor:02d}"
        structure_gate = structure_ids[end_floor]
        base = 2000 + zone_number * 200
        facade = f"H{base + 10:04d}"
        partitions = f"H{base + 20:04d}"
        elec = f"H{base + 30:04d}"
        hydraulic_fire = f"H{base + 40:04d}"
        mechanical = f"H{base + 50:04d}"
        rough_inspection = f"H{base + 60:04d}"
        linings = f"H{base + 70:04d}"
        ceilings = f"H{base + 80:04d}"
        finishes = f"H{base + 90:04d}"
        joinery = f"H{base + 100:04d}"
        fitoff = f"H{base + 110:04d}"

        zone_specs.extend([
            (facade, "4.1.1", names["4.1"], f"{zone_label} facade brackets, glazing and weather seal", "construction", 20, "Facade", [structure_gate, "H0070"]),
            (partitions, "6.1.1", names["6.1"], f"{zone_label} set-out, partitions and wall framing", "construction", 15, "Partitions", [structure_gate]),
            (elec, "5.1.1", names["5.1"], f"{zone_label} electrical, data and security rough-in", "construction", 12, "Electrical/Data", [partitions]),
            (hydraulic_fire, "5.1.2", names["5.1"], f"{zone_label} hydraulic and fire services rough-in", "construction", 12, "Hydraulic/Fire", [partitions]),
            (mechanical, "5.1.3", names["5.1"], f"{zone_label} mechanical ductwork, VAVs and controls rough-in", "construction", 15, "Mechanical", [partitions, "H0090"]),
            (rough_inspection, "5.1.4", names["5.1"], f"{zone_label} rough-in inspection and close-in approval", "inspection", 2, "Certifier", [elec, hydraulic_fire, mechanical]),
            (linings, "6.1.2", names["6.1"], f"{zone_label} insulation, plasterboard linings and stopping", "construction", 18, "Linings", [rough_inspection, facade]),
            (ceilings, "6.1.3", names["6.1"], f"{zone_label} ceiling grid, access panels and service coordination", "construction", 10, "Ceilings", [linings, mechanical]),
            (finishes, "6.1.4", names["6.1"], f"{zone_label} paint, wall finishes and floor finishes", "construction", 18, "Finishes", [linings, ceilings, facade]),
            (joinery, "6.1.5", names["6.1"], f"{zone_label} joinery, doors, hardware and fixtures", "construction", 20, "Joinery/Builder", [finishes]),
            (fitoff, "6.1.6", names["6.1"], f"{zone_label} services fit-off, testing and balancing", "commissioning", 15, "Services", [joinery, "H0100"]),
        ])

    specs.extend(zone_specs)
    zone_fitoffs = [item[0] for item in zone_specs if "services fit-off" in item[3]]
    zone_facades = [item[0] for item in zone_specs if "facade brackets" in item[3]]

    specs.extend([
        ("H8000", "7.1.1", names["7.1"], "Lift rail installation, car installation and controls", "construction", 60, "Lift Contractor", ["H0080", previous_structure]),
        ("H8010", "7.1.2", names["7.1"], "Permanent power energisation and main switchboard commissioning", "commissioning", 20, "Electrical", ["H0100", previous_structure]),
        ("H8020", "7.1.3", names["7.1"], "Mechanical plant installation and controls integration", "construction", 35, "Mechanical", ["H0090", previous_structure]),
        ("H8030", "8.1.1", names["8.1"], "Mechanical testing, balancing and seasonal commissioning allowance", "commissioning", 35, "Mechanical", [*zone_fitoffs, "H8020"]),
        ("H8040", "8.1.2", names["8.1"], "Fire mode, EWIS, sprinklers and life-safety systems testing", "commissioning", 25, "Fire Services", [*zone_fitoffs, "H0100"]),
        ("H8050", "8.1.3", names["8.1"], "Lift commissioning, registration and emergency interfaces", "commissioning", 25, "Lift Contractor", ["H8000", "H8010"]),
        ("H8060", "8.1.4", names["8.1"], "Facade completion, water testing and defect close-out", "inspection", 20, "Facade", zone_facades),
        ("H8070", "8.1.5", names["8.1"], "Integrated services commissioning and authority witness testing", "commissioning", 35, "Services", ["H8010", "H8030", "H8040", "H8050"]),
        ("H8080", "8.1.6", names["8.1"], "Final inspections, occupancy certification and compliance documentation", "inspection", 25, "Certifier", ["H8060", "H8070"]),
        ("H8090", "8.1.7", names["8.1"], "Defects rectification, cleaning and client demonstrations", "construction", 25, "Builder", ["H8080"]),
        ("H8100", "8.1.8", names["8.1"], "Practical completion inspection", "inspection", 5, "Project Manager", ["H8090"]),
        ("H8110", "8.1.9", names["8.1"], "Handover, manuals, warranties and operations onboarding", "handover", 5, "Project Manager", ["H8100"]),
    ])

    specs = _split_specs(specs, {
        "H0140": [
            ("H0140", "Soft strip, hazardous material controls and demolition preparation", 15),
            ("H0145", "Demolition, hard strip and site clearance", 15),
        ],
        "H0150": [
            ("H0150", "Retention system installation and capping beam", 20),
            ("H0155", "Retention monitoring, survey controls and certification", 15),
        ],
        "H0160": [
            ("H0160", "Bulk excavation stage 1 and spoil removal", 15),
            ("H0165", "Bulk excavation stage 2 and spoil removal", 15),
            ("H0168", "Bulk excavation stage 3 trim and working platform", 15),
        ],
        "H0170": [
            ("H0170", "Piling stage 1 and reinforcement cages", 15),
            ("H0175", "Piling stage 2, concrete placement and records", 15),
            ("H0178", "Pile testing, trimming and acceptance", 10),
        ],
        "H0180": [
            ("H0180", "Pile caps and starter reinforcement", 15),
            ("H0185", "Raft reinforcement, embeds and inspections", 10),
            ("H0188", "Raft concrete pour and cure allowance", 10),
        ],
        "H0190": [
            ("H0190", "Basement lower walls, columns and slab", 20),
            ("H0195", "Basement upper walls, columns and podium supports", 20),
            ("H0198", "Basement waterproofing, drainage and backfill interfaces", 15),
        ],
        "H0200": [
            ("H0200", "Ground floor transfer formwork and temporary works", 15),
            ("H0205", "Ground floor transfer reinforcement and embeds", 10),
            ("H0208", "Ground floor transfer concrete pour and cure", 10),
        ],
        "H8000": [
            ("H8000", "Lift rails, brackets and shaft equipment installation", 20),
            ("H8005", "Lift car, doors and machine room installation", 20),
            ("H8008", "Lift controls, safety devices and pre-commissioning", 20),
        ],
        "H8020": [
            ("H8020", "Mechanical plant set-down and major equipment installation", 20),
            ("H8025", "Mechanical controls, pipework and integration checks", 15),
        ],
        "H8030": [
            ("H8030", "Mechanical testing and balancing", 20),
            ("H8035", "Seasonal commissioning allowance and performance tuning", 15),
        ],
        "H8070": [
            ("H8070", "Integrated services commissioning dry run", 20),
            ("H8075", "Authority witness testing and life-safety integration", 15),
        ],
    })

    return _build_wbs_from_specs(specs, names), _activities_from_specs(specs), []


def _fallback_schedule(project_type=None, storeys=None, gfa=None):
    if project_type in {"high_rise_commercial", "high_rise_residential"}:
        return _highrise_commercial_template(storeys=storeys, gfa=gfa)
    if project_type in {"fitout", "refurbishment"}:
        return _fitout_template()
    return _building_template()


def _project_calendar_id():
    basis = st.session_state.get("planning_basis")
    if not basis:
        return "VIC_5DAY_STANDARD_2026"
    location_default = default_calendar_for_location(getattr(basis, "location", None))
    if location_default != "VIC_5DAY_STANDARD_2026" and getattr(basis, "calendar_id", None) == "VIC_5DAY_STANDARD_2026":
        basis.calendar_id = location_default
    return getattr(basis, "calendar_id", None) or location_default


def _apply_project_calendar(project):
    calendar_id = _project_calendar_id()
    for activity in project.activities:
        activity.calendar_id = calendar_id
    return project


def _project_context_text():
    basis = st.session_state.get("planning_basis")
    interpretation = st.session_state.get("interpretation") or {}
    return " ".join([
        str(st.session_state.get("project_brief") or ""),
        str(getattr(basis, "project_description", "") if basis else ""),
        str(interpretation.get("project_name") or ""),
        str(interpretation.get("summary") or ""),
        str(interpretation.get("new_build_or_refurb") or ""),
    ]).lower()


def _project_type_value():
    basis = st.session_state.get("planning_basis")
    interpretation = st.session_state.get("interpretation") or {}
    storeys = getattr(basis, "storeys", None) if basis else None
    gfa = getattr(basis, "gfa_m2", None) if basis else None
    storeys = storeys or interpretation.get("storeys")
    gfa = gfa or interpretation.get("gfa_m2")

    try:
        storeys = int(float(storeys)) if storeys not in (None, "") else None
    except (TypeError, ValueError):
        storeys = None
    try:
        gfa = float(str(gfa).replace(",", "")) if gfa not in (None, "") else None
    except (TypeError, ValueError):
        gfa = None

    if (storeys and storeys >= 10) or (gfa and gfa >= 10000):
        context_text = _project_context_text()
        residential_use = any(term in context_text for term in RESIDENTIAL_USE_TERMS)
        commercial_use = any(term in context_text for term in COMMERCIAL_USE_TERMS)
        if commercial_use and not residential_use:
            return "high_rise_commercial"
        return "high_rise_residential"

    if basis and basis.project_type:
        return basis.project_type.value
    return interpretation.get("project_type")


def _activity_text(activity):
    return f"{activity.activity_name} {activity.wbs_name} {activity.trade or ''}".lower()


def _find_matching_activities(activities, keywords):
    matches = []
    for activity in activities:
        text = _activity_text(activity)
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword.lower()).replace(r"\ ", r"\s+") + r"\b"
            if re.search(pattern, text):
                matches.append(activity)
                break
    return matches


def _add_predecessors(activity, predecessor_ids):
    existing = {pred.activity_id for pred in activity.predecessors}
    for predecessor_id in predecessor_ids:
        if predecessor_id != activity.activity_id and predecessor_id not in existing:
            activity.predecessors.append(Predecessor(activity_id=predecessor_id))
            existing.add(predecessor_id)


def _repair_schedule_logic(project):
    """Add common missing links that make generated schedules usable for CPM review."""
    activities = project.activities
    rough_in = _find_matching_activities(
        activities,
        ["electrical rough", "plumbing rough", "hvac rough", "mechanical hvac rough", "services rough", "data and communications rough", "fire services rough"],
    )
    lining_targets = _find_matching_activities(activities, ["plasterboard", "lining", "gyprock"])
    for target in lining_targets:
        _add_predecessors(target, [a.activity_id for a in rough_in])

    waterproofing = _find_matching_activities(activities, ["waterproof"])
    tiling_targets = [a for a in _find_matching_activities(activities, ["tile", "tiling"]) if "waterproof" not in _activity_text(a)]
    for target in tiling_targets:
        _add_predecessors(target, [a.activity_id for a in waterproofing if a.activity_id != target.activity_id])

    envelope = _find_matching_activities(activities, ["roofing", "roof covering", "roof structure", "envelope", "cladding", "weatherproof"])
    moisture_targets = [
        activity for activity in _find_matching_activities(
            activities,
            ["paint", "floor finish", "floor finishes", "flooring", "internal finish", "carpet", "timber floor"],
        )
        if not any(word in _activity_text(activity) for word in ["remove", "demolish", "strip-out"])
    ]
    for target in moisture_targets:
        _add_predecessors(target, [a.activity_id for a in envelope if a.activity_id != target.activity_id])

    final_candidates = _find_matching_activities(activities, ["handover", "practical completion", "occupancy"])
    final_activity = final_candidates[-1] if final_candidates else None
    successor_ids = {pred.activity_id for act in activities for pred in act.predecessors}
    terminal = [
        act for act in activities
        if act.activity_id not in successor_ids
        and act.activity_type != ActivityType.MILESTONE
        and act.activity_id != (final_activity.activity_id if final_activity else None)
    ]

    if final_activity and terminal:
        _add_predecessors(final_activity, [act.activity_id for act in terminal])
    elif len(terminal) > 1:
        project.activities.append(Activity(
            activity_id="A999",
            wbs_code="8.9.9",
            wbs_name="Completion and Handover / Practical Completion",
            activity_name="Practical completion milestone",
            activity_type=ActivityType.MILESTONE,
            duration_optimistic_days=0,
            duration_most_likely_days=0,
            duration_pessimistic_days=0,
            predecessors=[Predecessor(activity_id=act.activity_id) for act in terminal],
            trade="Project Manager",
            human_review_required=True,
            assumption="Completion milestone added to close open terminal activities.",
        ))

    return project


def _build_project_from_generated_data(raw_data):
    wbs_elements = _sanitize_wbs_elements(raw_data)
    activities = _sanitize_activities(raw_data)
    procurement_items = _sanitize_procurement_items(raw_data)

    project_type = _project_type_value()
    if project_type == "high_rise_commercial":
        minimum_activity_count = 90
        minimum_wbs_count = 30
        max_one_day_share = 0.05
    else:
        minimum_activity_count = 35
        minimum_wbs_count = 12
        max_one_day_share = 0.25

    one_day_count = sum(1 for activity in activities if activity.duration_most_likely_days <= 1)
    one_day_share = one_day_count / len(activities) if activities else 1
    generated_duration_sum = sum(activity.duration_most_likely_days for activity in activities)
    highrise_duration_too_short = project_type == "high_rise_commercial" and generated_duration_sum < 650

    if (
        len(wbs_elements) < minimum_wbs_count
        or len(activities) < minimum_activity_count
        or one_day_share > max_one_day_share
        or highrise_duration_too_short
    ):
        generated_activity_count = len(activities)
        generated_wbs_count = len(wbs_elements)
        wbs_elements, activities, procurement_items = _fallback_schedule(project_type)
        st.session_state.schedule_generation_note = (
            f"The AI schedule output was too broad ({generated_activity_count} activities, "
            f"{generated_wbs_count} WBS items), or had unrealistic short durations. "
            "A benchmark-based editable teaching template was inserted for planner review."
        )
    else:
        st.session_state.schedule_generation_note = None

    project = Project(
        project_name=st.session_state.interpretation.get("project_name", "Untitled"),
        planning_basis=st.session_state.planning_basis,
        project_start_date=st.session_state.project_start_date or datetime.date(2026, 7, 1),
        wbs_elements=wbs_elements,
        activities=activities,
        procurement_items=procurement_items,
    )
    return _apply_project_calendar(_repair_schedule_logic(project))


def _build_project_from_benchmark_template(project_type):
    basis = st.session_state.get("planning_basis")
    interpretation = st.session_state.get("interpretation") or {}
    storeys = getattr(basis, "storeys", None) if basis else None
    gfa = getattr(basis, "gfa_m2", None) if basis else None
    storeys = storeys or interpretation.get("storeys")
    gfa = gfa or interpretation.get("gfa_m2")
    wbs_elements, activities, procurement_items = _fallback_schedule(
        project_type,
        storeys=storeys,
        gfa=gfa,
    )
    label = _format_label(project_type)
    st.session_state.schedule_generation_note = (
        f"A benchmark-based {label.lower()} teaching template was inserted immediately "
        "for planner review. This avoids waiting for an external AI schedule draft for "
        "large tower projects and keeps the CPM network fully editable."
    )
    project = Project(
        project_name=st.session_state.interpretation.get("project_name", "Untitled"),
        planning_basis=st.session_state.planning_basis,
        project_start_date=st.session_state.project_start_date or datetime.date(2026, 7, 1),
        wbs_elements=wbs_elements,
        activities=activities,
        procurement_items=procurement_items,
    )
    return _apply_project_calendar(_repair_schedule_logic(project))


def _reset_schedule_for_regeneration():
    st.session_state.project = None
    st.session_state.schedule_generated = False
    st.session_state.schedule_approved = False
    st.session_state.cpm_calculated = False
    st.session_state.schedule_generation_note = None


def _approve_schedule():
    st.session_state.schedule_approved = True
    st.session_state.current_step = 5
    st.session_state.selected_page = "Export"
    st.session_state._nav_synced_step = 5


def _activity_table(project):
    rows = []
    for a in project.activities:
        rows.append({
            "ID": a.activity_id,
            "Activity": a.activity_name,
            "WBS": a.wbs_code,
            "Type": _format_label(a.activity_type.value),
            "Trade": a.trade or "",
            "Duration": a.duration_most_likely_days,
            "Predecessors": ", ".join([p.activity_id for p in a.predecessors]),
            "Start": a.early_start,
            "Finish": a.early_finish,
            "Float": a.total_float,
            "Critical": "Yes" if a.is_critical else "No",
        })
    return pd.DataFrame(rows)


def _sync_activity_edits(project, edited_df):
    current = {a.activity_id: a for a in project.activities}
    updated = []

    for idx, row in edited_df.fillna("").iterrows():
        activity_id = str(row.get("ID") or f"A{(idx + 1) * 10:03d}").strip()
        if not activity_id:
            continue
        existing = current.get(activity_id)
        duration = _to_int(row.get("Duration"), default=existing.duration_most_likely_days if existing else 1)
        predecessors = _parse_predecessors(row.get("Predecessors"))

        if existing:
            existing.activity_name = str(row.get("Activity") or existing.activity_name)
            existing.wbs_code = str(row.get("WBS") or existing.wbs_code)
            existing.trade = str(row.get("Trade") or existing.trade or "")
            existing.duration_most_likely_days = duration
            existing.duration_optimistic_days = min(existing.duration_optimistic_days or duration, duration)
            existing.duration_pessimistic_days = max(existing.duration_pessimistic_days or duration, duration)
            existing.predecessors = predecessors
            updated.append(existing)
        else:
            updated.append(Activity(
                activity_id=activity_id,
                wbs_code=str(row.get("WBS") or "1"),
                wbs_name="Planner-added Activity",
                activity_name=str(row.get("Activity") or "Planner-added activity"),
                activity_type=ActivityType.CONSTRUCTION,
                trade=str(row.get("Trade") or "General"),
                duration_optimistic_days=max(0, duration - 1),
                duration_most_likely_days=duration,
                duration_pessimistic_days=duration + 2,
                predecessors=predecessors,
                human_review_required=True,
                assumption="Added or edited by planner in schedule review.",
            ))

    project.activities = updated
    project.validation_results = []
    project.p50_completion = None
    project.p80_completion = None
    return _apply_project_calendar(project)


def _render_validation_results(results):
    summary = get_validation_summary(results)
    if summary["total"] == 0:
        st.success("No validation issues found.")
        return summary

    status = f"{summary['errors']} errors · {summary['warnings']} warnings · {summary['info']} info"
    if summary["has_blocking_errors"]:
        st.error(status)
    else:
        st.warning(status)

    rows = [
        {
            "Severity": v.severity.value,
            "Finding": v.description,
            "Activities": ", ".join(v.affected_activities),
            "Suggested action": v.suggested_fix or "",
        }
        for v in results
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    return summary


def _render_duration_basis(project_type):
    if project_type in {"high_rise_commercial", "high_rise_residential"}:
        label = "high-rise residential" if project_type == "high_rise_residential" else "high-rise commercial"
        st.info(
            f"Duration basis: {label} benchmark template. The template uses "
            "7-10 working days per typical structural floor cycle, long-lead facade/lift/"
            "plant procurement, and a multi-month commissioning/certification allowance. "
            "Durations remain AACE Class 5/4 planning values and should be checked with "
            "local subcontractors, productivity rates, and project-specific quantities."
        )
    elif project_type in {"fitout", "refurbishment"}:
        st.info(
            "Duration basis: fit-out/refurbishment benchmark template with separate "
            "strip-out, partition framing, MEP/F rough-in, linings, finishes, fit-off, "
            "commissioning, defects, and handover activities."
        )
    else:
        st.info(
            "Duration basis: building benchmark template informed by residential/custom "
            "home sample schedules and CPM training examples, then scaled for project "
            "type, storeys, and scope uncertainty."
        )


def _format_completion_date(value):
    if value is None:
        return "Not available"
    return f"{value:%d %b %Y}"


def _completion_caption(project, value):
    if value is None:
        return ""
    calendar_id = project.planning_basis.calendar_id if project.planning_basis else "VIC_5DAY_STANDARD_2026"
    cal = load_calendar_from_library(calendar_id)
    working_days = cal.working_days_between(project.project_start_date, value)
    calendar_days = max(0, (value - project.project_start_date).days)
    return (
        f"{value.isoformat()} · {working_days:,} working days "
        f"· {calendar_days / 7:.1f} calendar weeks from start"
    )


def _working_days_to(project, value):
    if value is None:
        return None
    calendar_id = project.planning_basis.calendar_id if project.planning_basis else "VIC_5DAY_STANDARD_2026"
    cal = load_calendar_from_library(calendar_id)
    return cal.working_days_between(project.project_start_date, value)


def _calendar_label(project):
    calendar_id = project.planning_basis.calendar_id if project.planning_basis else "VIC_5DAY_STANDARD_2026"
    return get_available_calendars().get(calendar_id, calendar_id)


def _render_completion_summary(project):
    p50_days = _working_days_to(project, project.p50_completion)
    p80_days = _working_days_to(project, project.p80_completion)
    buffer_days = (p80_days - p50_days) if p50_days is not None and p80_days is not None else None

    st.markdown("#### Project Duration")
    st.caption(
        "One CPM schedule is being reported at two confidence levels: P50 is the most-likely CPM finish; "
        "P80 adds planning contingency for schedule uncertainty."
    )

    c1, c2, c3 = st.columns([1.15, 1.15, 0.9])
    with c1:
        st.metric(
            "Most-Likely Duration (P50)",
            f"{p50_days:,} working days" if p50_days is not None else "Not available",
            f"Finish {_format_completion_date(project.p50_completion)}",
        )
        st.caption(_completion_caption(project, project.p50_completion))
    with c2:
        st.metric(
            "Risk-Adjusted Duration (P80)",
            f"{p80_days:,} working days" if p80_days is not None else "Not available",
            f"Finish {_format_completion_date(project.p80_completion)}",
        )
        st.caption(_completion_caption(project, project.p80_completion))
    with c3:
        st.metric(
            "Risk Allowance",
            f"+{buffer_days:,} working days" if buffer_days is not None else "Not available",
            "P80 minus P50",
        )
        location = project.planning_basis.location if project.planning_basis else None
        st.caption(f"Calendar: {_calendar_label(project)}" + (f" · Location: {location}" if location else ""))


def render():
    st.markdown("## 📊 Step 4: Construction Schedule")

    if not st.session_state.planning_basis_approved:
        st.warning("⚠️ Please approve the Planning Basis in Step 3 first.")
        return

    if not st.session_state.schedule_generated or st.session_state.project is None:
        progress = st.progress(0, text="Preparing schedule inputs")
        project_type = _project_type_value()

        if project_type in {"high_rise_commercial", "high_rise_residential"}:
            progress.progress(35, text="Loading high-rise benchmark CPM template")
            st.session_state.project = _build_project_from_benchmark_template(project_type)
            st.session_state.schedule_generated = True
            progress.progress(100, text="Draft schedule ready for review")
        else:

            # Load production rates for LLM context
            rates_path = os.path.join(APP_DIR, "libraries", "production_rates.csv")
            rates = pd.read_csv(rates_path).to_dict('records') if os.path.exists(rates_path) else []
            progress.progress(15, text="Loading production rates and WBS templates")

            # Load WBS template
            templates_path = os.path.join(APP_DIR, "libraries", "wbs_templates.json")
            templates = {}
            if os.path.exists(templates_path):
                with open(templates_path) as f:
                    templates = json.load(f)

            p_type = st.session_state.planning_basis.project_type.value
            template = templates.get(p_type)
            progress.progress(35, text="Generating detailed WBS and activity list")

            raw_data = generate_wbs_and_activities(
                st.session_state.planning_basis.model_dump(mode="json"),
                rates,
                template
            )

            progress.progress(70, text="Checking schedule detail and repairing common logic gaps")
            st.session_state.project = _build_project_from_generated_data(raw_data or {})
            st.session_state.schedule_generated = True
            progress.progress(100, text="Draft schedule ready for review")

    project = st.session_state.project
    if st.session_state.get("schedule_generation_note"):
        st.info(st.session_state.schedule_generation_note)
    _render_duration_basis(_project_type_value())

    st.markdown("### 📅 Draft Schedule Review")
    st.markdown("Review the generated WBS and activity list. You can edit individual activities before calculating the critical path.")

    top1, top2, top3, top4 = st.columns(4)
    with top1:
        st.metric("Activities", len(project.activities))
    with top2:
        st.metric("WBS Items", len(project.wbs_elements))
    with top3:
        st.metric("Procurement Items", len(project.procurement_items))
    with top4:
        st.metric("Start Date", str(project.project_start_date))

    st.button(
        "Regenerate Detailed Schedule",
        key="regenerate_detailed_schedule",
        help="Replace the current draft with a new granular WBS/activity schedule.",
        on_click=_reset_schedule_for_regeneration,
    )

    # Display WBS elements
    with st.expander("🏗️ Work Breakdown Structure", expanded=False):
        wbs_df = pd.DataFrame([
            {
                "Code": e.wbs_code,
                "Parent": e.parent_code or "",
                "Name": e.name,
                "Level": e.level,
                "Description": e.description or "",
                "Confidence": e.confidence_level.value,
            }
            for e in project.wbs_elements
        ])
        st.dataframe(wbs_df, use_container_width=True, hide_index=True)

    # Display and Edit Activities
    st.markdown("#### Activities")
    edited_df = st.data_editor(
        _activity_table(project),
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Duration": st.column_config.NumberColumn("Duration", min_value=0, step=1, format="%d days"),
            "Start": st.column_config.DateColumn("Start", disabled=True),
            "Finish": st.column_config.DateColumn("Finish", disabled=True),
            "Float": st.column_config.NumberColumn("Float", disabled=True, format="%d"),
            "Critical": st.column_config.TextColumn("Critical", disabled=True),
        },
    )

    # Sync edits back to project object (simplified)
    if st.button("💾 Save Edits & Calculate CPM"):
        progress = st.progress(0, text="Saving activity edits")
        project = _sync_activity_edits(project, edited_df)
        progress.progress(20, text="Repairing common dependency gaps")
        project = _repair_schedule_logic(project)
        progress.progress(40, text="Calculating early and late dates")
        project = run_cpm(project)
        progress.progress(60, text="Running construction logic validation")
        project.validation_results = validate_project(project)

        # Generate narratives
        progress.progress(80, text="Drafting basis of schedule narrative")
        project.basis_of_schedule_narrative = generate_basis_of_schedule(
            project.planning_basis.model_dump(mode="json"),
            len(project.activities)
        )

        st.session_state.project = project
        st.session_state.cpm_calculated = True
        progress.progress(100, text="CPM calculation complete")
        st.success("CPM Calculation Complete")

    if st.session_state.cpm_calculated:
        st.markdown("---")
        _render_completion_summary(project)

        critical_df = _activity_table(project)
        critical_df = critical_df[critical_df["Critical"] == "Yes"]
        with st.expander("Critical path activities", expanded=True):
            if critical_df.empty:
                st.info("No critical path activities were identified.")
            else:
                st.dataframe(
                    critical_df[["ID", "Activity", "Trade", "Duration", "Start", "Finish", "Float"]],
                    use_container_width=True,
                    hide_index=True,
                )
        
        st.markdown("#### Validation Results")
        summary = _render_validation_results(project.validation_results)

        if project.procurement_items:
            with st.expander("Procurement register", expanded=False):
                st.dataframe(
                    pd.DataFrame([
                        {
                            "ID": item.item_id,
                            "Category": _format_label(item.item_category),
                            "Description": item.description,
                            "Install Activity": item.installation_activity_id or "",
                            "Lead Time": (
                                f"{item.total_lead_weeks_min}-{item.total_lead_weeks_max} weeks"
                                if item.total_lead_weeks_min and item.total_lead_weeks_max
                                else "Planner review"
                            ),
                        }
                        for item in project.procurement_items
                    ]),
                    use_container_width=True,
                    hide_index=True,
                )

        approve_disabled = summary["has_blocking_errors"] or not project.p50_completion or not project.p80_completion
        if approve_disabled:
            st.caption("Resolve blocking validation errors and calculate completion dates before approving the schedule.")

        st.button(
            "Next: Approve Schedule & Export ➡️",
            type="primary",
            disabled=approve_disabled,
            key="approve_schedule_to_export",
            on_click=_approve_schedule,
        )
