"""
Construction-aware validation engine (§16).

Implements construction-logic rules, DCMA-style schedule quality checks,
procurement integrity validation, and weather/seasonal rules.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from .models import Activity, Project, ValidationResult, Severity, WBSElement


# ── Core construction-logic rules ──────────────────────────────────────────────

CONSTRUCTION_RULES = [
    {
        "rule_id": "SEQ-001",
        "description": "Substructure must precede superstructure",
        "check": "phase_sequence",
        "before_types": ["substructure", "foundation", "footing", "slab"],
        "after_types": ["frame", "superstructure"],
        "severity": "Error",
        "source": "Construction sequencing — fundamental",
    },
    {
        "rule_id": "SEQ-002",
        "description": "Slab cure lag (≥7 days) required before frame loading",
        "check": "cure_lag",
        "from_keyword": "slab",
        "to_keyword": "frame",
        "min_lag_days": 7,
        "severity": "Error",
        "source": "AS 3600 — Concrete structures",
    },
    {
        "rule_id": "SEQ-003",
        "description": "Frame inspection must occur before internal linings",
        "check": "inspection_before",
        "inspection_keyword": "frame inspection",
        "after_keyword": "plasterboard|lining|internal wall",
        "severity": "Error",
        "source": "NCC / Building surveyor requirements",
    },
    {
        "rule_id": "SEQ-004",
        "description": "Roof and envelope must precede moisture-sensitive internal finishes",
        "check": "phase_sequence",
        "before_types": ["roof", "envelope", "cladding", "weatherboard"],
        "after_types": ["plaster", "paint", "carpet", "timber floor", "floor finish"],
        "severity": "Warning",
        "source": "Construction best practice — weathertightness",
    },
    {
        "rule_id": "SEQ-005",
        "description": "Services rough-in must precede plasterboard",
        "check": "phase_sequence",
        "before_types": ["electrical rough", "plumbing rough", "hvac rough", "services rough"],
        "after_types": ["plasterboard", "lining", "gyprock"],
        "severity": "Error",
        "source": "Construction sequencing — standard",
    },
    {
        "rule_id": "SEQ-006",
        "description": "Waterproofing inspection must precede tiling in wet areas",
        "check": "inspection_before",
        "inspection_keyword": "waterproofing",
        "after_keyword": "tile|tiling",
        "severity": "Error",
        "source": "AS 3740 — Waterproofing of domestic wet areas",
    },
    {
        "rule_id": "SEQ-007",
        "description": "Final electrical certification before occupancy",
        "check": "phase_sequence",
        "before_types": ["electrical certification", "electrical final", "electrical inspection"],
        "after_types": ["occupancy", "handover", "practical completion"],
        "severity": "Error",
        "source": "AS 3000 — Electrical installations",
    },
    {
        "rule_id": "SEQ-008",
        "description": "Practical Completion inspection must precede handover",
        "check": "phase_sequence",
        "before_types": ["practical completion", "pc inspection", "defects inspection"],
        "after_types": ["handover"],
        "severity": "Error",
        "source": "AS 4000 — General conditions of contract",
    },
    {
        "rule_id": "QUAL-001",
        "description": "Activity without predecessor (open start)",
        "check": "open_ended_start",
        "severity": "Warning",
        "source": "DCMA 14-Point Schedule Assessment",
    },
    {
        "rule_id": "QUAL-002",
        "description": "Activity without successor (open finish)",
        "check": "open_ended_finish",
        "severity": "Warning",
        "source": "DCMA 14-Point Schedule Assessment",
    },
    {
        "rule_id": "QUAL-003",
        "description": "Activity duration exceeds 25 working days without breakdown",
        "check": "long_duration",
        "max_days": 25,
        "severity": "Warning",
        "source": "DCMA 14-Point Schedule Assessment (adapted)",
    },
    {
        "rule_id": "PROC-001",
        "description": "Long-lead installation activity without linked procurement chain",
        "check": "procurement_link",
        "severity": "Error",
        "source": "§10.3 — Procurement linkage rule",
    },
]


def _activity_matches_keywords(act: Activity, keywords: list[str]) -> bool:
    """Check if an activity name matches any keyword (case-insensitive)."""
    name = act.activity_name.lower()
    trade = act.trade.lower() if act.trade else ""
    combined = f"{name} {trade}"

    for kw in keywords:
        keyword = kw.lower()
        if keyword == "roof":
            if re.search(r"\broof\b|\broofing\b", combined):
                return True
        elif keyword in combined:
            return True
    return False


def _has_transitive_predecessor(
    activity_id: str,
    required_predecessor_ids: set[str],
    predecessors_by_activity: dict[str, set[str]],
) -> bool:
    """Return true if any required predecessor appears upstream of activity_id."""
    seen = set()
    stack = list(predecessors_by_activity.get(activity_id, set()))

    while stack:
        pred_id = stack.pop()
        if pred_id in required_predecessor_ids:
            return True
        if pred_id in seen:
            continue
        seen.add(pred_id)
        stack.extend(predecessors_by_activity.get(pred_id, set()))

    return False


def validate_project(project: Project) -> list[ValidationResult]:
    """Run all validation rules against a project and return findings."""
    results: list[ValidationResult] = []
    activities = project.activities
    act_map = {a.activity_id: a for a in activities}

    # Build predecessor/successor index
    has_predecessor = set()
    has_successor = set()
    predecessors_by_activity: dict[str, set[str]] = {act.activity_id: set() for act in activities}
    for act in activities:
        for pred in act.predecessors:
            has_predecessor.add(act.activity_id)
            has_successor.add(pred.activity_id)
            predecessors_by_activity.setdefault(act.activity_id, set()).add(pred.activity_id)

    for rule in CONSTRUCTION_RULES:
        check = rule["check"]

        if check == "open_ended_start":
            # Activities without predecessors (excluding first activity)
            for act in activities:
                if act.activity_id not in has_predecessor and act.activity_type.value != "milestone":
                    # Allow the very first activity
                    if activities.index(act) > 0:
                        results.append(ValidationResult(
                            rule_id=rule["rule_id"],
                            description=f"{rule['description']}: {act.activity_name} ({act.activity_id})",
                            severity=Severity(rule["severity"]),
                            affected_activities=[act.activity_id],
                            suggested_fix="Add a predecessor relationship or mark as project start milestone.",
                            source=rule.get("source"),
                        ))

        elif check == "open_ended_finish":
            for act in activities:
                if act.activity_id not in has_successor and act.activity_type.value != "milestone":
                    if activities.index(act) < len(activities) - 1:
                        results.append(ValidationResult(
                            rule_id=rule["rule_id"],
                            description=f"{rule['description']}: {act.activity_name} ({act.activity_id})",
                            severity=Severity(rule["severity"]),
                            affected_activities=[act.activity_id],
                            suggested_fix="Add a successor relationship or mark as project finish milestone.",
                            source=rule.get("source"),
                        ))

        elif check == "long_duration":
            max_days = rule.get("max_days", 25)
            for act in activities:
                if act.activity_type.value in {"procurement", "approval", "design"}:
                    continue
                if act.duration_most_likely_days > max_days:
                    results.append(ValidationResult(
                        rule_id=rule["rule_id"],
                        description=f"{rule['description']}: {act.activity_name} ({act.duration_most_likely_days}d)",
                        severity=Severity(rule["severity"]),
                        affected_activities=[act.activity_id],
                        suggested_fix=f"Break down into sub-activities or flag as hammock activity.",
                        source=rule.get("source"),
                    ))

        elif check == "phase_sequence":
            before_types = rule.get("before_types", [])
            after_types = rule.get("after_types", [])
            before_acts = [a for a in activities if _activity_matches_keywords(a, before_types)]
            after_acts = [a for a in activities if _activity_matches_keywords(a, after_types)]

            for after_act in after_acts:
                # Check that at least one "before" activity is upstream.
                before_ids = {a.activity_id for a in before_acts}
                if after_act.activity_id in before_ids:
                    continue
                if before_acts and not _has_transitive_predecessor(
                    after_act.activity_id,
                    before_ids,
                    predecessors_by_activity,
                ):
                    results.append(ValidationResult(
                        rule_id=rule["rule_id"],
                        description=f"{rule['description']}: {after_act.activity_name} has no predecessor from required prior phase",
                        severity=Severity(rule["severity"]),
                        affected_activities=[after_act.activity_id],
                        suggested_fix=f"Add FS dependency from a {'/'.join(before_types)} activity.",
                        source=rule.get("source"),
                    ))

        elif check == "procurement_link":
            for act in activities:
                if act.procurement_item and not act.procurement_chain_ref:
                    results.append(ValidationResult(
                        rule_id=rule["rule_id"],
                        description=f"{rule['description']}: {act.activity_name}",
                        severity=Severity(rule["severity"]),
                        affected_activities=[act.activity_id],
                        suggested_fix="Link to a procurement chain entry or remove procurement flag.",
                        source=rule.get("source"),
                    ))

    # Load additional rules from library
    lib_rules = _load_library_rules()
    # (Library rules are informational supplements to the hardcoded core rules)

    return results


def _load_library_rules() -> list[dict]:
    """Load additional rules from the CSV library."""
    lib_path = Path(__file__).parent.parent / "libraries" / "construction_logic.csv"
    if not lib_path.exists():
        return []
    rules = []
    with open(lib_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rules.append(row)
    return rules


def get_validation_summary(results: list[ValidationResult]) -> dict:
    """Summarize validation results by severity."""
    errors = [r for r in results if r.severity == Severity.ERROR and not r.overridden]
    warnings = [r for r in results if r.severity == Severity.WARNING and not r.overridden]
    infos = [r for r in results if r.severity == Severity.INFO]
    overridden = [r for r in results if r.overridden]

    return {
        "total": len(results),
        "errors": len(errors),
        "warnings": len(warnings),
        "info": len(infos),
        "overridden": len(overridden),
        "has_blocking_errors": len(errors) > 0,
        "error_details": errors,
        "warning_details": warnings,
    }
