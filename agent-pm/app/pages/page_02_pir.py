"""Page 2: Conversational Project Information Request (PIR)."""

import streamlit as st
from core.llm_service import generate_pir_questions


def _go_to_basis():
    st.session_state.current_step = 3
    st.session_state.selected_page = "Planning Basis"
    st.session_state._nav_synced_step = 3


def render():
    st.markdown("## 💬 Step 2: Project Information Request")

    if not st.session_state.interpretation:
        st.warning("⚠️ Please complete Step 1 (Project Brief) first.")
        return

    interp = st.session_state.interpretation
    st.markdown(
        f"**Project:** {interp.get('project_name', 'New Project')} · "
        f"**Type:** {interp.get('project_type', 'unknown').replace('_', ' ').title()}"
    )
    st.markdown(
        "The agent asks questions progressively, prioritised by schedule risk. "
        "You can accept defaults, override values, or mark items as unknown."
    )

    st.divider()

    # Generate questions if needed
    if not st.session_state.pir_questions:
        with st.spinner("🤖 Generating project-specific questions..."):
            questions = generate_pir_questions(interp, st.session_state.pir_answers)
            st.session_state.pir_questions = questions

    # Display questions as structured inputs
    questions = st.session_state.pir_questions

    if not questions:
        st.info("No further questions needed. Proceed to Planning Basis.")
        st.button(
            "✅ Proceed to Planning Basis ➡️",
            type="primary",
            key="proceed_to_basis_empty",
            on_click=_go_to_basis,
        )
        return

    st.markdown(f"### Round {st.session_state.pir_round + 1} — Questions")

    for i, q in enumerate(questions):
        with st.container():
            st.markdown(f"**{q.get('label', f'Question {i+1}')}**")

            # "Why this default?" expander
            col1, col2 = st.columns([3, 1])
            with col2:
                with st.expander("ℹ️ Why this default?"):
                    st.caption(f"**Default:** {q.get('default_value', 'N/A')}")
                    st.caption(f"**Rationale:** {q.get('default_rationale', 'N/A')}")
                    st.caption(f"**Schedule impact:** {q.get('schedule_impact', 'N/A')}")
                    st.caption(f"**Source:** {q.get('source', 'N/A')}")

            with col1:
                name = q.get("name", f"q_{i}")
                input_type = q.get("input_type", "text")
                default = q.get("default_value")
                options = q.get("options", [])
                current_val = st.session_state.pir_answers.get(name, default)

                if input_type == "select" and options:
                    idx = options.index(str(current_val)) if str(current_val) in options else 0
                    val = st.selectbox(
                        f"Select value for {name}",
                        options=options,
                        index=idx,
                        key=f"pir_{name}",
                        label_visibility="collapsed",
                    )
                elif input_type == "radio" and options:
                    val = st.radio(
                        f"Select for {name}",
                        options=options,
                        key=f"pir_{name}",
                        horizontal=True,
                        label_visibility="collapsed",
                    )
                elif input_type == "number":
                    val = st.number_input(
                        f"Value for {name}",
                        value=int(default) if default else 0,
                        key=f"pir_{name}",
                        label_visibility="collapsed",
                    )
                else:
                    val = st.text_input(
                        f"Value for {name}",
                        value=str(default) if default else "",
                        key=f"pir_{name}",
                        label_visibility="collapsed",
                    )

                st.session_state.pir_answers[name] = val

                # Unknown handling
                unknown = st.checkbox(
                    "Mark as Unknown",
                    key=f"unknown_{name}",
                )
                if unknown:
                    handling = st.radio(
                        "How to handle:",
                        ["Use conservative assumption", "Flag as high risk"],
                        key=f"handling_{name}",
                        horizontal=True,
                        label_visibility="collapsed",
                    )
                    st.session_state.pir_answers[f"{name}_status"] = (
                        "unknown_conservative" if "conservative" in handling else "unknown_high_risk"
                    )

            st.divider()

    # Actions
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("🔄 Ask More Questions", use_container_width=True):
            st.session_state.pir_round += 1
            with st.spinner("Generating additional questions..."):
                new_qs = generate_pir_questions(interp, st.session_state.pir_answers)
                st.session_state.pir_questions = new_qs
            st.rerun()

    with col_c:
        st.button(
            "✅ Complete PIR → Planning Basis ➡️",
            type="primary",
            use_container_width=True,
            key="complete_pir_to_basis",
            on_click=_go_to_basis,
        )

    # Show all answers so far
    if st.session_state.pir_answers:
        with st.expander("📋 All answers so far", expanded=False):
            for k, v in st.session_state.pir_answers.items():
                if not k.endswith("_status"):
                    status = st.session_state.pir_answers.get(f"{k}_status", "confirmed")
                    st.markdown(f"- **{k}**: {v} _({status})_")
