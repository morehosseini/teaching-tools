"""Page 1: Project Brief Input."""

import streamlit as st
from core.llm_service import interpret_project_brief
import datetime


EXAMPLE_BRIEFS = {
    "Two-storey house in Kew": (
        "New two-storey detached house in Kew, Melbourne. Approximately 280m² GFA. "
        "Timber frame construction with brick veneer. Concrete tile roof. "
        "4 bedrooms, 3 bathrooms, double garage. Site is flat with good access. "
        "Planning permit already obtained."
    ),
    "Townhouse development in Brunswick": (
        "Three townhouses on a subdivided lot in Brunswick. Each approximately 160m² GFA, "
        "three storeys. Timber frame with rendered cladding. Flat metal roof. "
        "Basement car parking for 6 cars. Site is relatively flat, narrow frontage."
    ),
    "Small office fit-out in CBD": (
        "Commercial office fit-out in Melbourne CBD. Level 12 of an existing building. "
        "Approximately 400m² NLA. Open plan with 2 meeting rooms, kitchen, and reception. "
        "Existing services to be modified. Tenant works only."
    ),
    "Warehouse in Dandenong South": (
        "New industrial warehouse in Dandenong South. Approximately 2000m² GFA. "
        "Steel portal frame, concrete slab, metal cladding. Small office area (~200m²). "
        "Loading dock for 2 trucks. Site is greenfield with services available."
    ),
}


def _go_to_pir():
    st.session_state.current_step = 2
    st.session_state.selected_page = "Information Request"
    st.session_state._nav_synced_step = 2


def render():
    st.markdown("## 📝 Step 1: Project Brief")
    st.markdown(
        "Enter a brief description of your construction project. "
        "The agent will interpret the brief, classify the project, and begin "
        "asking the right questions."
    )

    # Example briefs
    with st.expander("📋 Example briefs (click to use)", expanded=False):
        cols = st.columns(2)
        for i, (title, text) in enumerate(EXAMPLE_BRIEFS.items()):
            with cols[i % 2]:
                if st.button(f"Use: {title}", key=f"example_{i}", use_container_width=True):
                    st.session_state.project_brief = text

    # Brief input
    brief = st.text_area(
        "Project Description",
        value=st.session_state.project_brief,
        height=200,
        placeholder="Describe your construction project here...\n\nInclude: project type, location, size, structural system, special features, constraints...",
    )
    st.session_state.project_brief = brief

    # Project start date
    col1, col2 = st.columns(2)
    with col1:
        default_start = st.session_state.project_start_date or datetime.date(2026, 7, 1)
        start_date = st.date_input(
            "Planned Start Date",
            value=default_start,
            help="When is construction planned to commence?",
        )
        st.session_state.project_start_date = start_date
    with col2:
        output_use = st.selectbox(
            "Output Purpose",
            ["Teaching / Learning", "Feasibility Study", "Internal Planning", "Research Demonstration"],
            help="How will this planning output be used?",
        )

    st.divider()

    # Submit
    col_a, col_b = st.columns([3, 1])
    with col_b:
        submitted = st.button(
            "🚀 Interpret Brief & Start PIR",
            type="primary",
            use_container_width=True,
            disabled=len(brief.strip()) < 20,
        )

    if submitted and brief.strip():
        with st.spinner("🤖 Interpreting your project brief with Gemini..."):
            interpretation = interpret_project_brief(brief)
            st.session_state.interpretation = interpretation
            st.session_state.current_step = 2

        # Show interpretation
        st.success("✅ Project brief interpreted successfully!")

        if interpretation:
            st.markdown("### 🔍 Project Interpretation")
            col1, col2, col3 = st.columns(3)
            with col1:
                ptype = interpretation.get("project_type") or "Unknown"
                st.metric("Project Type", ptype.replace("_", " ").title())
            with col2:
                gfa = interpretation.get("gfa_m2")
                if gfa is not None:
                    gfa_display = f"{int(gfa):,} m²" if float(gfa) == int(gfa) else f"{gfa:,.1f} m²"
                else:
                    gfa_display = "TBD"
                st.metric("Est. GFA", gfa_display)
            with col3:
                rprof = interpretation.get("risk_profile") or "Medium"
                st.metric("Risk Profile", rprof.title())

            st.markdown(f"**Summary:** {interpretation.get('summary') or ''}")

            if interpretation.get("missing_critical_info"):
                st.warning("**Missing critical information** (will be asked in PIR):")
                for item in interpretation["missing_critical_info"]:
                    st.markdown(f"  - {item}")

            st.divider()
            st.button(
                "Next: Information Request ➡️",
                type="primary",
                use_container_width=True,
                key="next_to_pir_after_interpret",
                on_click=_go_to_pir,
            )

    elif st.session_state.interpretation:
        st.success("✅ Brief already interpreted.")
        st.divider()
        st.button(
            "Next: Information Request ➡️",
            type="primary",
            use_container_width=True,
            key="next_to_pir_existing",
            on_click=_go_to_pir,
        )
