"""Page 3: Planning Basis Summary and Approval Gate."""

import streamlit as st
from core.calendar_engine import default_calendar_for_location
from core.llm_service import generate_planning_basis_summary
from core.models import PlanningBasis, ProjectType
import datetime


def _project_type_from_interpretation(value):
    try:
        return ProjectType(value)
    except (TypeError, ValueError):
        return ProjectType.DETACHED_HOUSE


def _go_to_schedule():
    st.session_state.current_step = 4
    st.session_state.selected_page = "Schedule"
    st.session_state._nav_synced_step = 4


def _approve_planning_basis():
    st.session_state.planning_basis_approved = True
    st.session_state.planning_basis.approved = True
    st.session_state.planning_basis.approved_at = datetime.datetime.now()
    _go_to_schedule()


def _answer_or_interpreted(name, interp):
    value = st.session_state.pir_answers.get(name)
    if value in (None, ""):
        return interp.get(name)
    return value


def _sync_planning_basis_with_interpretation():
    basis = st.session_state.planning_basis
    interp = st.session_state.interpretation or {}
    if basis is None:
        return

    location = interp.get("location") or basis.location
    basis.location = location
    basis.calendar_id = default_calendar_for_location(location)

    if basis.gfa_m2 in (None, "") and interp.get("gfa_m2") not in (None, ""):
        basis.gfa_m2 = interp.get("gfa_m2")
    if basis.storeys in (None, "") and interp.get("storeys") not in (None, ""):
        basis.storeys = interp.get("storeys")

    summary = "\n".join(basis.assumptions or [])
    if location and "melbourne" not in location.lower() and "melbourne" in summary.lower():
        with st.spinner("Refreshing Planning Basis Summary for the project location..."):
            basis.assumptions = [
                generate_planning_basis_summary(
                    st.session_state.interpretation,
                    st.session_state.pir_answers,
                )
            ]


def render():
    st.markdown("## 📄 Step 3: Planning Basis Summary")

    if st.session_state.current_step < 3:
        st.warning("⚠️ Please complete the previous steps first.")
        return

    st.markdown(
        "Review the planning basis summary below. This document lists every assumption, "
        "default, source, and uncertainty. You must explicitly approve this before the "
        "agent proceeds to generate the WBS and activity list."
    )

    if st.session_state.planning_basis is None:
        with st.spinner("🤖 Generating Planning Basis Summary..."):
            summary_text = generate_planning_basis_summary(
                st.session_state.interpretation, 
                st.session_state.pir_answers
            )
            
            # Construct PlanningBasis object
            interp = st.session_state.interpretation
            location = interp.get("location")
            st.session_state.planning_basis = PlanningBasis(
                project_type=_project_type_from_interpretation(interp.get("project_type")),
                project_description=st.session_state.project_brief,
                location=location,
                gfa_m2=_answer_or_interpreted("gfa_m2", interp),
                storeys=_answer_or_interpreted("storeys", interp),
                structural_system=_answer_or_interpreted("structural_system", interp),
                soil_class=st.session_state.pir_answers.get("soil_class"),
                calendar_id=default_calendar_for_location(location),
                assumptions=[summary_text] # For now, store the whole text
            )

    _sync_planning_basis_with_interpretation()

    st.markdown("---")
    st.markdown(st.session_state.planning_basis.assumptions[0])
    st.markdown("---")

    if not st.session_state.planning_basis_approved:
        col1, col2 = st.columns([3, 1])
        with col2:
            with st.form("planning_basis_approval_form", clear_on_submit=True):
                st.form_submit_button(
                    "✅ Approve Planning Basis",
                    type="primary",
                    use_container_width=True,
                    on_click=_approve_planning_basis,
                )
    else:
        st.success("✅ Planning Basis Approved")
        st.button(
            "Next: Schedule Generation ➡️",
            type="primary",
            key="go_to_schedule_once",
            on_click=_go_to_schedule,
        )
