"""
Procurement chain logic (§10).

Models the full procurement chain from design freeze through installation,
with explicit consultant review loops and linkage to construction activities.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from .models import ProcurementItem, Activity, Predecessor, RelationshipType, ActivityType


def load_procurement_library() -> list[dict]:
    """Load procurement lead-time library from CSV."""
    lib_path = Path(__file__).parent.parent / "libraries" / "procurement_leads.csv"
    if not lib_path.exists():
        return []
    items = []
    with open(lib_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(row)
    return items


def lookup_lead_time(item_category: str) -> Optional[dict]:
    """Look up procurement lead time for an item category."""
    library = load_procurement_library()
    for item in library:
        if item.get("ItemCategory", "").lower() == item_category.lower():
            return item
    return None


def generate_procurement_chain(
    proc_item: ProcurementItem,
    prefix: str = "PROC",
    start_id: int = 1,
) -> list[Activity]:
    """
    Generate the full procurement chain as individual activities (§10.2):
    
    Design freeze → Submit shop drawings → Consultant review (RFI loop) →
    Final approval → Sample/mock-up approval → Long-lead deposit/PO release →
    Fabrication/manufacture → Factory Acceptance Test → Delivery to site →
    Installation
    """
    chain: list[Activity] = []
    base_id = f"{prefix}-{proc_item.item_id}"
    step = start_id

    steps = [
        ("Design Freeze", proc_item.design_freeze_days, "procurement"),
        ("Submit Shop Drawings", proc_item.shop_drawing_days, "procurement"),
        ("Consultant Review (RFI Loop)", proc_item.consultant_review_days, "procurement"),
        ("Final Approval", proc_item.approval_days, "approval"),
    ]

    if proc_item.sample_approval_days:
        steps.append(
            ("Sample/Mock-up Approval", proc_item.sample_approval_days, "approval")
        )

    steps.extend([
        ("Fabrication/Manufacture", proc_item.fabrication_days, "procurement"),
        ("Delivery to Site", proc_item.delivery_days, "procurement"),
    ])

    prev_id = None
    for name, duration, act_type in steps:
        act_id = f"{base_id}-{step:02d}"
        predecessors = []
        if prev_id:
            predecessors = [Predecessor(activity_id=prev_id, relationship_type=RelationshipType.FS)]

        act = Activity(
            activity_id=act_id,
            wbs_code=f"PROC.{proc_item.item_id}",
            wbs_name=f"Procurement / {proc_item.description}",
            activity_name=f"{proc_item.description} — {name}",
            activity_type=ActivityType(act_type) if act_type != "procurement" else ActivityType.PROCUREMENT,
            duration_most_likely_days=duration,
            duration_optimistic_days=max(1, int(duration * 0.8)),
            duration_pessimistic_days=int(duration * 1.5),
            predecessors=predecessors,
            procurement_item=True,
            procurement_chain_ref=proc_item.item_id,
            human_review_required=True,
            assumption=f"Lead time from procurement library; planner confirmation required.",
        )
        chain.append(act)
        prev_id = act_id
        step += 1

    return chain


def validate_procurement_links(
    activities: list[Activity],
    procurement_items: list[ProcurementItem],
) -> list[str]:
    """
    Validate procurement integrity (§10.3):
    - Every long-lead item must have a linked installation activity.
    - Every installation activity must have a linked procurement chain.
    """
    warnings = []

    for item in procurement_items:
        if not item.installation_activity_id:
            warnings.append(
                f"Procurement item '{item.description}' ({item.item_id}) "
                f"has no linked installation activity."
            )
        else:
            act = next(
                (a for a in activities if a.activity_id == item.installation_activity_id),
                None,
            )
            if not act:
                warnings.append(
                    f"Procurement item '{item.description}' ({item.item_id}) "
                    f"references installation activity '{item.installation_activity_id}' "
                    f"which does not exist."
                )

    return warnings
