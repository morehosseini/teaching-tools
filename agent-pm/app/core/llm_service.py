"""
Gemini LLM service layer for the Construction Planning Agent.

Handles all LLM interactions using Google's Gemini 3.1 Pro API:
- Project interpretation from brief descriptions
- Conversational PIR generation
- WBS and activity generation (library-grounded)
- Basis of Schedule narrative
- Critical path narrative

The LLM is NOT responsible for CPM calculations, float, dates,
calendar arithmetic, or resource optimisation (§14).
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional, Union




def _get_client():
    """Lazy-initialize the Gemini client."""
    try:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return None
        client = genai.Client(api_key=api_key)
        return client
    except ImportError:
        return None


MODEL_ID = "gemini-2.5-pro"  # Will be updated when gemini-3.1-pro SDK is available


def _coerce_number(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _extract_storeys_from_text(text: str) -> Optional[int]:
    patterns = [
        r"(\d+)\s*[- ]?\s*storey",
        r"(\d+)\s*[- ]?\s*story",
        r"(\d+)\s*[- ]?\s*levels?",
        r"(\d+)\s*[- ]?\s*floors?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_per_floor_area(text: str) -> Optional[float]:
    """Extract per-floor area from brief text (e.g. 'each floor 780 m2')."""
    patterns = [
        r"each\s+(?:floor|level|storey|story)\s+(?:is\s+)?(?:approx(?:imately)?\s+)?(\d[\d,]*)\s*m(?:²|2)",
        r"(\d[\d,]*)\s*m(?:²|2)\s+(?:per|each|a)\s+(?:floor|level|storey|story)",
        r"(?:floor|level|storey|story)\s+(?:area|size)\s+(?:of\s+)?(?:approx(?:imately)?\s+)?(\d[\d,]*)\s*m(?:²|2)",
        r"(?:typical\s+)?floor\s+plate\s+(?:of\s+)?(?:approx(?:imately)?\s+)?(\d[\d,]*)\s*m(?:²|2)",
        r"(\d[\d,]*)\s*m(?:²|2)\s+(?:typical\s+)?floor\s+plate",
        r"(?:with|at)\s+(?:each\s+)?(?:floor|level)\s+(\d[\d,]*)\s*m(?:²|2)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _extract_location_from_text(text: str) -> Optional[str]:
    """Pull out common Australian city/state locations when the LLM misses them."""
    lower = (text or "").lower()
    known_locations = [
        ("Adelaide", ["adelaide", "south australia", " sa"]),
        ("Melbourne", ["melbourne", "victoria", " vic"]),
        ("Sydney", ["sydney", "new south wales", " nsw"]),
        ("Brisbane", ["brisbane", "queensland", " qld"]),
        ("Perth", ["perth", "western australia", " wa"]),
        ("Hobart", ["hobart", "tasmania", " tas"]),
        ("Canberra", ["canberra", "act"]),
        ("Darwin", ["darwin", "northern territory", " nt"]),
    ]
    for label, terms in known_locations:
        if any(term in lower for term in terms):
            return label
    return None


RESIDENTIAL_USE_TERMS = [
    "residential",
    "apartment",
    "apartments",
    "unit",
    "units",
    "dwelling",
    "dwellings",
    "build to rent",
    "build-to-rent",
    "student accommodation",
]

COMMERCIAL_USE_TERMS = [
    "office",
    "commercial",
    "retail",
    "workplace",
    "hotel",
    "hospitality",
    "mixed-use",
    "mixed use",
]


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _normalise_project_classification(result: dict, brief: str) -> dict:
    """Correct obvious scale misclassifications before downstream scheduling."""
    if not isinstance(result, dict):
        return result

    storeys = result.get("storeys") or _extract_storeys_from_text(brief)
    gfa = _coerce_number(result.get("gfa_m2"))
    combined = " ".join(str(result.get(key, "")) for key in ["project_name", "summary", "new_build_or_refurb"])
    text = f"{brief} {combined}".lower()
    brief_location = _extract_location_from_text(brief)
    result_location = _extract_location_from_text(str(result.get("location") or ""))
    if brief_location and (not result.get("location") or result_location != brief_location):
        result["location"] = brief_location

    try:
        storeys_int = int(float(storeys)) if storeys not in (None, "") else None
    except (TypeError, ValueError):
        storeys_int = None

    # Cross-check GFA: if brief explicitly states storeys and per-floor area,
    # use deterministic calculation instead of trusting LLM arithmetic.
    brief_storeys = _extract_storeys_from_text(brief)
    brief_floor_area = _extract_per_floor_area(brief)
    if brief_storeys and brief_floor_area:
        calculated_gfa = brief_storeys * brief_floor_area
        gfa = calculated_gfa
        result["gfa_m2"] = calculated_gfa
        if storeys_int is None or storeys_int != brief_storeys:
            storeys_int = brief_storeys
            result["storeys"] = brief_storeys

    is_high_rise_scale = bool((storeys_int and storeys_int >= 10) or (gfa and gfa >= 10000))
    is_residential_use = _contains_any(text, RESIDENTIAL_USE_TERMS)
    is_commercial_use = _contains_any(text, COMMERCIAL_USE_TERMS)

    if is_high_rise_scale and (is_residential_use or is_commercial_use):
        result["project_type"] = (
            "high_rise_commercial"
            if is_commercial_use and not is_residential_use
            else "high_rise_residential"
        )
        result["risk_profile"] = "high"
        if storeys_int:
            result["storeys"] = storeys_int
        if gfa:
            result["gfa_m2"] = gfa

        missing = result.get("missing_critical_info") or []
        scale_notes = [
            "Tower crane, hoist, loading dock, and CBD logistics strategy",
            "Facade system and procurement lead times",
            "Lift strategy and vertical transportation commissioning",
            "Basement, retention, piling, and ground conditions",
            "Services riser, plantroom, fire, and authority commissioning requirements",
        ]
        if result["project_type"] == "high_rise_residential":
            scale_notes.extend([
                "Apartment mix, typical-floor layout, and wet-area stacking strategy",
                "Common areas, amenities, waste rooms, and residential occupancy permit requirements",
            ])
        result["missing_critical_info"] = list(dict.fromkeys([*missing, *scale_notes]))

    return result


def _call_gemini(prompt: str, system_instruction: str = "", temperature: float = 0.3) -> str:
    """Call Gemini API and return text response."""
    client = _get_client()
    if client is None:
        return _fallback_response(prompt)

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config={
                "temperature": temperature,
                "system_instruction": system_instruction,
            },
        )
        return response.text
    except Exception as e:
        return f"[LLM Error: {str(e)}]"


def _call_gemini_json(prompt: str, system_instruction: str = "") -> Optional[Union[dict, list]]:
    """Call Gemini and parse the response as JSON."""
    full_prompt = (
        f"{prompt}\n\n"
        "IMPORTANT: Respond ONLY with valid JSON. No markdown, no code fences, no explanation."
    )
    response = _call_gemini(full_prompt, system_instruction, temperature=0.2)

    # Clean response
    text = response.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _clean_narrative_response(response: str) -> str:
    """Convert accidental JSON/code-fenced narrative responses into readable prose."""
    text = (response or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(parsed, str):
        return parsed

    if isinstance(parsed, dict):
        preferred_keys = [
            "narrative",
            "summary",
            "basis_of_schedule",
            "critical_path_narrative",
            "content",
            "text",
        ]
        for key in preferred_keys:
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        sections = []
        for key, value in parsed.items():
            label = key.replace("_", " ").title()
            if isinstance(value, str):
                sections.append(f"**{label}**\n\n{value}")
            elif isinstance(value, list):
                items = "\n".join(f"- {item}" for item in value)
                sections.append(f"**{label}**\n\n{items}")
        if sections:
            return "\n\n".join(sections)

    if isinstance(parsed, list):
        lines = []
        for item in parsed:
            if isinstance(item, str):
                lines.append(f"- {item}")
            elif isinstance(item, dict):
                label = item.get("title") or item.get("heading") or item.get("name")
                body = item.get("body") or item.get("text") or item.get("summary")
                if label and body:
                    lines.append(f"**{label}**\n\n{body}")
                else:
                    lines.append("- " + "; ".join(f"{k}: {v}" for k, v in item.items()))
        if lines:
            return "\n\n".join(lines)

    return text


# ── System instructions ────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are a construction planning assistant for the Australian 
construction industry, supporting residential and commercial projects at early-stage
AACE Class 5/4 maturity.

KEY RULES:
1. You NEVER invent production rates, lead times, or construction-logic rules.
   If a value is not provided, flag "not in library — planner input required."
2. You always distinguish between: user-provided info, LLM inference (flagged),
   library data, defaults applied, and calculated results.
3. Every duration must have a traceable source.
4. You surface uncertainty, don't hide it.
5. You produce structured JSON output that can be validated by Pydantic schemas.
6. You are assisting a human planner, not replacing them.
7. Construction context: Australian standards (NCC, AS series). Use state-specific
   planning, public-holiday, and regulatory assumptions only when the project location
   supports them. Do not replace a user-provided location with Melbourne/Victoria.
"""


# ── Project interpretation ─────────────────────────────────────────────────────

def interpret_project_brief(brief: str) -> dict:
    """
    Interpret a project brief and extract key project information.
    Returns structured data about project type, scope, and initial assumptions.
    """
    prompt = f"""Interpret this construction project brief and extract key information.

PROJECT BRIEF:
{brief}

Return a JSON object with these fields:
{{
    "project_type": "one of: detached_house, townhouse, medium_density, high_rise_residential, small_commercial, high_rise_commercial, warehouse, school_extension, fitout, refurbishment, community_facility",
    "project_name": "descriptive name",
    "location": "suburb/area if mentioned, else null",
    "gfa_m2": approximate GFA in m² if inferable, else null,
    "storeys": number of storeys if mentioned, else null,
    "structural_system": "if mentioned, else null",
    "basement": true/false,
    "new_build_or_refurb": "new_build, refurbishment, extension, or fitout",
    "key_features": ["list of notable features mentioned"],
    "constraints_mentioned": ["list of any constraints mentioned"],
    "missing_critical_info": ["list of critical information NOT in the brief that must be asked"],
    "risk_profile": "low, medium, or high based on complexity",
    "summary": "one paragraph professional interpretation"
}}
"""
    result = _call_gemini_json(prompt, SYSTEM_INSTRUCTION)
    if result is None:
        return _normalise_project_classification(_default_interpretation(brief), brief)
    return _normalise_project_classification(result, brief)


# ── PIR generation ─────────────────────────────────────────────────────────────

def generate_pir_questions(
    interpretation: dict,
    already_answered: Optional[dict] = None,
) -> list[dict]:
    """
    Generate the next batch of PIR questions based on project interpretation
    and what's already been answered. Progressive disclosure — not all at once.
    """
    answered_str = json.dumps(already_answered or {}, indent=2, default=str)
    interp_str = json.dumps(interpretation, indent=2, default=str)

    prompt = f"""Based on this project interpretation and previously answered questions,
generate the NEXT 3-5 most important Project Information Request (PIR) questions.

PROJECT INTERPRETATION:
{interp_str}

ALREADY ANSWERED:
{answered_str}

Prioritize questions by schedule risk impact. For the identified project type,
ask only questions that MATERIALLY affect schedule outcomes.

Return a JSON array of question objects:
[
    {{
        "name": "variable_name_snake_case",
        "label": "Human readable question",
        "input_type": "select|number|text|radio",
        "options": ["option1", "option2"] (only for select/radio),
        "default_value": "reasonable Australian default for the stated project location",
        "default_rationale": "One sentence explaining why this default",
        "schedule_impact": "One sentence on how changing this affects the schedule",
        "source": "library|regional_default|llm_inference",
        "priority": "high|medium|low"
    }}
]

Focus on: soil class, structural system, site access, planning permits,
procurement, calendar, working hours — whichever are most relevant
for this project type and haven't been answered yet.
If the project is outside Victoria, do not use Melbourne/Victorian defaults unless
you explicitly mark them as a fallback requiring planner review.
"""
    result = _call_gemini_json(prompt, SYSTEM_INSTRUCTION)
    if result is None:
        return _default_pir_questions(interpretation)
    return result if isinstance(result, list) else []


# ── WBS and activity generation ────────────────────────────────────────────────

def generate_wbs_and_activities(
    planning_basis: dict,
    production_rates: list[dict],
    wbs_template: Optional[dict] = None,
) -> dict:
    """
    Generate WBS and activity list grounded in the planning basis and library rates.
    """
    basis_str = json.dumps(planning_basis, indent=2, default=str)
    rates_str = json.dumps(production_rates[:50], indent=2, default=str)  # Limit for token budget
    template_str = json.dumps(wbs_template or {}, indent=2, default=str)

    prompt = f"""Generate a Work Breakdown Structure and activity list for this project.

PLANNING BASIS:
{basis_str}

AVAILABLE PRODUCTION RATES (use these, do NOT invent rates):
{rates_str}

WBS TEMPLATE (if available):
{template_str}

RULES:
1. WBS is deliverable-based (what is being built), per PMBOK/ISO 21502.
2. Use 4-level hierarchy: Phase > Location > Trade > Activity.
3. Include: Site Works, Substructure, Superstructure, Envelope, Services Rough-in,
   Internal Finishes, External Works, Commissioning, Handover.
4. Include design, approvals, and procurement as parallel process groups.
5. Include authority inspections as zero-duration milestones.
6. For each activity, reference a production rate from the library if available.
   If not available, flag "not_in_library" and mark human_review_required.
7. Use three-point durations (optimistic, most_likely, pessimistic).
8. Tag location_zone and trade for every activity.
9. Generate a granular teaching schedule, not broad summary phases:
   - Fit-out/refurbishment: 45-70 activities.
   - Detached house/townhouse/small commercial: 45-80 activities.
   - High-rise residential/commercial: 90-140 activities with floor/zone breakdown.
   - Split services into electrical, data/comms, plumbing, mechanical/HVAC, fire where relevant.
   - Split finishes into linings, stopping, waterproofing, tiling, flooring, painting, joinery, doors/hardware, fixtures.
   - Include inspection, certification, testing, commissioning, cleaning, defects, and handover milestones.
10. Add enough direct FS predecessors that plasterboard/linings follow services rough-in,
    tiling follows waterproofing, final handover follows commissioning/defects, and terminal work packages
    feed a practical completion or handover milestone.
11. For high-rise residential/commercial work, use realistic benchmark logic:
    - 7-10 working days per typical structural floor cycle for preliminary planning.
    - Long-lead facade, lifts, switchboards, mechanical plant, fire systems, and structural steel procurement.
    - Commissioning/certification is substantial, typically measured in months, not days.

Return JSON:
{{
    "wbs_elements": [
        {{
            "wbs_code": "1",
            "parent_code": null,
            "name": "Site Works and Earthworks",
            "level": 1,
            "description": "...",
            "confidence_level": "Class 5"
        }}
    ],
    "activities": [
        {{
            "activity_id": "A010",
            "wbs_code": "1.1.1",
            "wbs_name": "Site Works / Setup / Preliminaries",
            "activity_name": "Site establishment and setup",
            "activity_type": "preliminary",
            "location_zone": "Whole site",
            "trade": "Builder",
            "quantity": null,
            "unit": null,
            "production_rate_source": "library:site_establishment_v2026.1",
            "duration_optimistic_days": 3,
            "duration_most_likely_days": 5,
            "duration_pessimistic_days": 8,
            "predecessors": [],
            "weather_sensitive": false,
            "human_review_required": true,
            "assumption": "Standard site setup; adjust for specific site constraints."
        }}
    ],
    "procurement_items": [
        {{
            "item_id": "P001",
            "item_category": "structural_steel",
            "description": "Structural steel members",
            "total_lead_weeks_min": 8,
            "total_lead_weeks_max": 12
        }}
    ]
}}
"""
    result = _call_gemini_json(prompt, SYSTEM_INSTRUCTION)
    if result is None:
        return {"wbs_elements": [], "activities": [], "procurement_items": []}
    return result


# ── Narrative generation ───────────────────────────────────────────────────────

def generate_basis_of_schedule(planning_basis: dict, activity_count: int) -> str:
    """Generate the Basis of Schedule narrative (§19 item 4)."""
    basis_str = json.dumps(planning_basis, indent=2, default=str)

    prompt = f"""Write a professional Basis of Schedule narrative for this project.

PLANNING BASIS:
{basis_str}

NUMBER OF ACTIVITIES: {activity_count}

The narrative should cover:
1. Scope basis and project description.
2. Methodology (CPM, production-rate-based durations, three-point estimates).
3. Calendar and working-time assumptions.
4. Productivity basis and key production rates.
5. Procurement assumptions.
6. Key exclusions and limitations.
7. AACE estimate class and confidence level.
8. Reference to Australian standards (NCC, AS series).

Write in professional construction planning language. 3-4 paragraphs.
Do not return JSON, markdown code fences, or file-style output.
"""
    return _clean_narrative_response(_call_gemini(prompt, SYSTEM_INSTRUCTION, temperature=0.4))


def generate_critical_path_narrative(
    critical_activities: list[dict],
    p50_weeks: float,
    p80_weeks: float,
) -> str:
    """Generate an annotated critical path narrative."""
    acts_str = json.dumps(critical_activities[:20], indent=2, default=str)

    prompt = f"""Write a critical path narrative for this construction schedule.

CRITICAL PATH ACTIVITIES:
{acts_str}

P50 DURATION: {p50_weeks:.1f} weeks
P80 DURATION: {p80_weeks:.1f} weeks

Explain:
1. The critical path sequence and why these activities drive the schedule.
2. Key risks on the critical path.
3. The difference between P50 and P80 and what drives the uncertainty range.
4. Potential acceleration opportunities.

Write in professional construction planning language. 2-3 paragraphs.
Do not return JSON, markdown code fences, or file-style output.
"""
    return _clean_narrative_response(_call_gemini(prompt, SYSTEM_INSTRUCTION, temperature=0.4))


def generate_planning_basis_summary(interpretation: dict, pir_answers: dict) -> str:
    """Generate the Planning Basis Summary narrative for user approval."""
    prompt = f"""Write a Planning Basis Summary for this project.

PROJECT INTERPRETATION:
{json.dumps(interpretation, indent=2, default=str)}

PIR ANSWERS:
{json.dumps(pir_answers, indent=2, default=str)}

This is the "contractual handshake" between the agent and the planner.
List every assumption, default, source, and uncertainty clearly.
Use a structured format with headings. Be concise but complete.
Preserve the user-provided project location. If the project is outside Victoria,
do not describe it as Melbourne/Victorian; use Australian/NCC framing and flag any
state-specific assumptions that still need local review.
Do not return JSON, markdown code fences, or file-style output.
"""
    return _clean_narrative_response(_call_gemini(prompt, SYSTEM_INSTRUCTION, temperature=0.3))


# ── Fallback responses (when API is unavailable) ──────────────────────────────

def _fallback_response(prompt: str) -> str:
    """Return a helpful message when the LLM is unavailable."""
    return (
        "[Gemini API not available. Please check your API key in the sidebar. "
        "The app will use default templates and library data instead.]"
    )


def _default_interpretation(brief: str) -> dict:
    """Default interpretation when LLM is unavailable."""
    return {
        "project_type": "detached_house",
        "project_name": "New Project",
        "location": _extract_location_from_text(brief) or "Australia",
        "gfa_m2": None,
        "storeys": None,
        "structural_system": None,
        "basement": False,
        "new_build_or_refurb": "new_build",
        "key_features": [],
        "constraints_mentioned": [],
        "missing_critical_info": [
            "Project type", "GFA", "Location", "Structural system",
            "Soil class", "Number of storeys"
        ],
        "risk_profile": "medium",
        "summary": f"Project from brief: {brief[:200]}. Further information required.",
    }


def _default_pir_questions(interpretation: dict) -> list[dict]:
    """Default PIR questions when LLM is unavailable."""
    return [
        {
            "name": "gfa_m2",
            "label": "What is the approximate Gross Floor Area (GFA) in m²?",
            "input_type": "number",
            "default_value": 250,
            "default_rationale": "Typical Australian detached house GFA; confirm against the brief.",
            "schedule_impact": "Directly affects all quantity-based duration calculations",
            "source": "regional_default",
            "priority": "high",
        },
        {
            "name": "structural_system",
            "label": "What is the primary structural system?",
            "input_type": "select",
            "options": [
                "Timber frame", "Steel frame", "Concrete frame",
                "Double brick", "Hybrid", "Other"
            ],
            "default_value": "Timber frame",
            "default_rationale": "Common Australian residential framing assumption (AS 1684 where applicable).",
            "schedule_impact": "Determines superstructure duration and trade sequence",
            "source": "regional_default",
            "priority": "high",
        },
        {
            "name": "soil_class",
            "label": "What is the soil class (AS 2870)?",
            "input_type": "select",
            "options": ["A", "S", "M", "H1", "H2", "E", "P", "Unknown"],
            "default_value": "M",
            "default_rationale": "Default soil class M assumed pending geotechnical advice.",
            "schedule_impact": "Changing to Class P adds approximately 5–10 working days to substructure",
            "source": "regional_default",
            "priority": "high",
        },
        {
            "name": "storeys",
            "label": "How many storeys (including ground floor)?",
            "input_type": "number",
            "default_value": 2,
            "default_rationale": "Typical low-rise residential default; confirm against the brief.",
            "schedule_impact": "Each additional storey adds 4-8 weeks to superstructure",
            "source": "regional_default",
            "priority": "high",
        },
        {
            "name": "calendar_type",
            "label": "What working calendar applies?",
            "input_type": "select",
            "options": [
                "5-day (Mon-Fri)",
                "5.5-day (Mon-Fri + Sat AM)",
                "6-day (Mon-Sat)",
                "5-day with RDOs"
            ],
            "default_value": "5-day (Mon-Fri)",
            "default_rationale": "Standard residential construction calendar",
            "schedule_impact": "6-day calendar reduces duration by ~17% vs 5-day",
            "source": "regional_default",
            "priority": "medium",
        },
    ]
