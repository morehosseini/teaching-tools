"""Page 5: Final Export and Sign-off."""

import streamlit as st
import pandas as pd
from core.excel_export import export_project_to_excel
from core.calendar_engine import default_calendar_for_location, get_available_calendars, load_calendar_from_library
from core.llm_service import generate_critical_path_narrative
from core.validation_engine import get_validation_summary


def _project_calendar_id(project):
    if not project.planning_basis:
        return "VIC_5DAY_STANDARD_2026"
    location_default = default_calendar_for_location(project.planning_basis.location)
    if location_default != "VIC_5DAY_STANDARD_2026" and project.planning_basis.calendar_id == "VIC_5DAY_STANDARD_2026":
        return location_default
    return project.planning_basis.calendar_id or location_default


def _format_completion_date(value):
    if value is None:
        return "Not available"
    return f"{value:%d %b %Y}"


def _completion_caption(project, value):
    if value is None:
        return ""
    calendar_id = _project_calendar_id(project)
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
    calendar_id = _project_calendar_id(project)
    cal = load_calendar_from_library(calendar_id)
    return cal.working_days_between(project.project_start_date, value)


def _calendar_label(project):
    calendar_id = _project_calendar_id(project)
    return get_available_calendars().get(calendar_id, calendar_id)


def _render_completion_summary(project):
    p50_days = _working_days_to(project, project.p50_completion)
    p80_days = _working_days_to(project, project.p80_completion)
    buffer_days = (p80_days - p50_days) if p50_days is not None and p80_days is not None else None

    st.markdown("### 🏁 Project Duration")
    st.info(
        "There is one CPM schedule, shown at two confidence levels. "
        "Use P50 as the most-likely target duration and P80 as the risk-adjusted planning duration."
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
    st.markdown("## 📑 Step 5: Final Planning Package")

    if not st.session_state.schedule_approved:
        st.warning("⚠️ Please approve the schedule in Step 4 first.")
        return

    project = st.session_state.project
    if project is None:
        st.error("No project schedule is available yet. Return to Step 4 and calculate the schedule first.")
        return

    if not project.p50_completion or not project.p80_completion:
        st.error("The schedule has not been calculated yet. Return to Step 4 and calculate CPM before exporting.")
        st.session_state.schedule_approved = False
        return

    _render_completion_summary(project)

    # Critical Path Narrative
    if project.critical_path_narrative is None:
        with st.spinner("🤖 Drafting Critical Path Narrative..."):
            critical_acts = [a.model_dump(mode="json") for a in project.activities if a.is_critical]
            # Calculate weeks for narrative
            total_days = (project.p50_completion - project.project_start_date).days
            p50_weeks = total_days / 7
            total_days_p80 = (project.p80_completion - project.project_start_date).days
            p80_weeks = total_days_p80 / 7
            
            project.critical_path_narrative = generate_critical_path_narrative(
                critical_acts,
                p50_weeks,
                p80_weeks
            )

    tab_summary, tab_path, tab_basis, tab_validation = st.tabs([
        "Summary",
        "Critical Path",
        "Basis of Schedule",
        "Validation",
    ])

    with tab_summary:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Activities", len(project.activities))
        with c2:
            st.metric("WBS Items", len(project.wbs_elements))
        with c3:
            st.metric("Procurement Items", len(project.procurement_items))
        with c4:
            st.metric("Schedule Version", project.schedule_version)

        st.markdown("#### Schedule Milestones")
        st.dataframe(
            pd.DataFrame([
                {"Milestone": "Project start", "Date": project.project_start_date},
                {"Milestone": "P50 completion", "Date": project.p50_completion},
                {"Milestone": "P80 completion", "Date": project.p80_completion},
            ]),
            use_container_width=True,
            hide_index=True,
        )

    with tab_path:
        st.markdown("#### Critical Path Narrative")
        st.markdown(project.critical_path_narrative or "Critical path narrative not yet available.")

        critical_rows = [
            {
                "ID": activity.activity_id,
                "Activity": activity.activity_name,
                "Trade": activity.trade or "",
                "Duration": activity.duration_most_likely_days,
                "Start": activity.early_start,
                "Finish": activity.early_finish,
            }
            for activity in project.activities
            if activity.is_critical
        ]
        if critical_rows:
            st.dataframe(pd.DataFrame(critical_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No critical path activities were identified.")

    with tab_basis:
        st.markdown("#### Basis of Schedule")
        st.markdown(project.basis_of_schedule_narrative or "Basis of Schedule not yet available.")

    with tab_validation:
        summary = get_validation_summary(project.validation_results)
        if summary["total"] == 0:
            st.success("No validation findings recorded.")
        else:
            st.markdown(f"**Validation status:** {summary['errors']} errors · {summary['warnings']} warnings · {summary['info']} info")
            st.dataframe(
                pd.DataFrame([
                    {
                        "Severity": item.severity.value,
                        "Finding": item.description,
                        "Activities": ", ".join(item.affected_activities),
                        "Suggested action": item.suggested_fix or "",
                    }
                    for item in project.validation_results
                ]),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    # Excel Export
    st.markdown("### 📥 Download Planning Package")
    st.markdown("Download the full 8-tab professional Excel workbook including WBS, Full Schedule, Procurement Register, and Validation Report.")

    excel_data = export_project_to_excel(project)
    
    st.download_button(
        label="📥 Download Excel Planning Package (.xlsx)",
        data=excel_data,
        file_name=f"Planning_Package_{project.project_name.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary"
    )

    st.divider()

    st.markdown("### ✍️ Planner Sign-Off")
    st.markdown("Please confirm the following to finalize the package:")
    
    c1 = st.checkbox("All high-uncertainty items reviewed and confirmed or adjusted")
    c2 = st.checkbox("Procurement lead times cross-checked with current supplier quotes")
    c3 = st.checkbox("Weather and calendar assumptions accepted for the project location and season")
    c4 = st.checkbox("Validation warnings reviewed and either accepted or mitigated")
    
    if c1 and c2 and c3 and c4:
        st.success("🎉 Planning Package Finalized. Ready for professional review.")
        st.balloons()
