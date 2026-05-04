"""
Construction Planning Agent — Streamlit Application
Main entry point with multi-page navigation and session state management.
"""

import streamlit as st
import os
import sys
from pathlib import Path

# Add app folder to path
sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="Construction Planning Agent",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

.stApp { font-family: 'Inter', sans-serif; }

.main-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 50%, #1a4a6e 100%);
    padding: 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    color: white;
}
.main-header h1 { color: white; margin: 0; font-size: 2rem; }
.main-header p { color: rgba(255,255,255,0.8); margin: 0.5rem 0 0; }

.step-indicator {
    display: flex;
    gap: 8px;
    margin: 1rem 0;
}
.step {
    flex: 1;
    padding: 10px;
    border-radius: 8px;
    text-align: center;
    font-size: 12px;
    font-weight: 600;
}
.step-active { background: #2d5a87; color: white; }
.step-done { background: #22c55e; color: white; }
.step-pending { background: #e2e8f0; color: #64748b; }

.disclaimer-box {
    background: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 8px;
    padding: 12px;
    font-size: 12px;
    color: #856404;
    margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Session state initialization ───────────────────────────────────────────────

def init_session_state():
    defaults = {
        "current_step": 1,
        "selected_page": "Project Brief",
        "_nav_synced_step": 1,
        "project_brief": "",
        "project_start_date": None,
        "interpretation": None,
        "pir_questions": [],
        "pir_answers": {},
        "pir_round": 0,
        "planning_basis": None,
        "planning_basis_approved": False,
        "project": None,
        "schedule_generated": False,
        "schedule_approved": False,
        "cpm_calculated": False,
        "chat_history": [],
        "gemini_api_key": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()


PAGE_OPTIONS = [
    "Project Brief",
    "Information Request",
    "Planning Basis",
    "Schedule",
    "Export",
    "Knowledge Base",
]

STEP_TO_PAGE = {
    1: "Project Brief",
    2: "Information Request",
    3: "Planning Basis",
    4: "Schedule",
    5: "Export",
}

PAGE_TO_STEP = {
    "Project Brief": 1,
    "Information Request": 2,
    "Planning Basis": 3,
    "Schedule": 4,
    "Export": 5,
}


def sync_page_from_step():
    """Keep button-driven workflow transitions aligned with the sidebar radio."""
    step = st.session_state.current_step
    if st.session_state.get("_nav_synced_step") != step:
        st.session_state.selected_page = STEP_TO_PAGE.get(step, "Project Brief")
        st.session_state._nav_synced_step = step


def sync_step_from_page():
    """Keep manual sidebar navigation aligned with the workflow progress marker."""
    page = st.session_state.selected_page
    if page in PAGE_TO_STEP:
        st.session_state.current_step = PAGE_TO_STEP[page]
        st.session_state._nav_synced_step = st.session_state.current_step


sync_page_from_step()


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/building-with-rooftop-terrace.png", width=64)
    st.markdown("### 🏗️ Construction Planning Agent")
    st.caption("ABPL90331 · Construction Technology")
    st.divider()

    # API Key management: Look in Streamlit Secrets, then Environment Variables
    gemini_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    os.environ["GEMINI_API_KEY"] = gemini_key
    st.session_state.gemini_api_key = gemini_key
    
    st.divider()

    # Progress
    st.markdown("### Progress")
    workflow_progress = max(0, min(st.session_state.current_step - 1, 4)) / 4
    st.progress(workflow_progress, text=f"Step {st.session_state.current_step} of 5")
    steps = [
        ("1. Project Brief", st.session_state.current_step > 1, st.session_state.current_step == 1),
        ("2. Information Request", st.session_state.current_step > 2, st.session_state.current_step == 2),
        ("3. Planning Basis", st.session_state.current_step > 3, st.session_state.current_step == 3),
        ("4. Schedule", st.session_state.current_step > 4, st.session_state.current_step == 4),
        ("5. Export", st.session_state.current_step > 5, st.session_state.current_step == 5),
    ]
    for label, done, active in steps:
        if done:
            st.markdown(f"✅ ~~{label}~~")
        elif active:
            st.markdown(f"▶️ **{label}**")
        else:
            st.markdown(f"⬜ {label}")

    st.divider()

    # Navigation
    st.markdown("### Navigation")
    nav = st.radio(
        "Go to step:",
        PAGE_OPTIONS,
        key="selected_page",
        on_change=sync_step_from_page,
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("v1.0 · Phase 1a")
    st.caption("AACE Class 5/4 outputs only")


# ── Page routing ───────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div class="main-header">
    <h1>🏗️ Construction Planning Agent</h1>
    <p>AI-assisted preliminary planning for construction projects · AACE Class 5/4</p>
</div>
""", unsafe_allow_html=True)

# Route to selected page
if nav == "Project Brief":
    from pages import page_01_brief
    page_01_brief.render()
elif nav == "Information Request":
    from pages import page_02_pir
    page_02_pir.render()
elif nav == "Planning Basis":
    from pages import page_03_basis
    page_03_basis.render()
elif nav == "Schedule":
    from pages import page_04_schedule
    page_04_schedule.render()
elif nav == "Export":
    from pages import page_05_export
    page_05_export.render()
elif nav == "Knowledge Base":
    from pages import page_06_knowledge
    page_06_knowledge.render()
