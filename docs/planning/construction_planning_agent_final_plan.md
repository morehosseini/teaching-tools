# Construction Planning and Scheduling Agent
## Final Intention and Development Plan

**Status:** Final consolidated version
**Date:** 3 May 2026
**Author:** Dr M. Reza Hosseini, Senior Lecturer in Construction Technology, Faculty of Architecture, Building and Planning, The University of Melbourne
**Incorporates:** Original concept, two rounds of construction-domain expert review, and a 30-year construction project manager critique

---

## 1. Intention and Framing

The intention is to develop an LLM-powered **construction planning assistant** that converts a brief project description into an auditable, editable, preliminary planning package for human review.

The defensible framing is:

> The agent scaffolds and accelerates the planner's first draft by asking the right project-information questions, surfacing assumptions, grounding durations in productivity logic, validating construction sequencing, and producing editable planning outputs for professional review.

This is explicitly a **human-in-the-loop planning support tool**, not an autonomous scheduler. A short project description does not contain enough information to produce a reliable construction programme. The agent must therefore surface uncertainty, request the information that materially affects schedule outcomes, and present a transparent first draft that a qualified planner can edit, validate, and approve.

The agent is positioned as practice-aligned rather than purely computer-science driven, and is designed to produce outputs typical of an AACE Class 5 or Class 4 estimate — i.e. concept-screening to feasibility-grade, not contract-grade.

---

## 2. Core Problem Being Addressed

Early-stage construction planning often starts from incomplete information: a brief project description, concept notes, a tender summary, a feasibility document, or a high-level client brief. Before a planner can prepare a meaningful programme, they must clarify scope, assumptions, site constraints, approvals, procurement requirements, productivity expectations, and construction logic.

The agent is intended to reduce the time required to move from:

```text
Brief project description
→ planner's structured first-draft planning package
```

It must support, not replace, the judgement of a construction planner or project manager. Adoption hinges on transparency: every duration, dependency, and assumption must be traceable to either user input, a named library source, or an explicit AI-generated inference flagged for review.

---

## 3. Reframed Workflow

```text
Brief construction project description
→ Conversational Project Information Request (PIR)
→ User confirms or overrides assumptions
→ Agent generates Planning Basis Summary
→ User explicitly approves Planning Basis
→ Agent generates WBS and activity list (library-grounded)
→ Agent applies production rates, calendars, and procurement lead times
→ Human reviews draft WBS, durations, and dependencies
→ Code validates schedule logic and construction rules
→ Code calculates calendar-aware CPM
→ Agent generates Basis of Schedule, registers, and Excel output
→ Planner Sign-Off checklist
→ Editable planning package issued
```

The first response from the agent is **never** a full schedule. It is a Project Information Request followed by a Planning Basis Summary that the user must approve before any WBS or activity is generated.

---

## 4. Project Information Request (PIR)

### 4.1 Conversational, progressive design

The PIR must not be presented as a 15-question form. Asked all at once, the user disengages or guesses. Instead, the PIR is structured as a **conversational, progressively disclosed elicitation**:

1. The LLM extracts everything it can from the initial prompt.
2. It classifies the likely project type and risk profile.
3. It asks only the PIR items that materially affect *that* project type, prioritised by schedule risk.
4. Each question is presented as a structured input (dropdown, radio, numeric field, or short text) so responses parse directly to JSON.

For example, if the prompt mentions "basement," the agent immediately queries soil class and retention system before asking about working calendar. If the prompt mentions "school extension during term," approvals and out-of-hours work permits are prioritised before procurement.

### 4.2 PIR variable inventory (conditional, by project type)

For residential or small commercial projects, the candidate PIR variables include:

- Project type and approximate gross floor area (GFA).
- Location: suburb, postcode, local council, climate zone.
- New build, refurbishment, extension, or fit-out.
- Number of storeys, basement status.
- Structural system and construction method.
- Soil class (AS 2870), geotechnical assumptions, slope.
- Site access constraints, neighbour and street conditions.
- Bushfire (BAL), flood, heritage, or planning overlays.
- Planning permit and building permit status.
- Required inspections and approval gates (council, building surveyor, plumbing, electrical, fire).
- Procurement route and form of contract (e.g. AS 4000, AS 2124, MBA/HIA fixed price, D&C).
- Long-lead items: structural steel, windows/glazing, switchboards, lifts, HVAC plant, joinery, façade, fire systems, specialist equipment.
- Working calendar: 5-day, 6-day, RDO pattern, shutdown assumptions.
- Required milestone dates.
- Output use: feasibility, tender, internal planning, teaching, research demonstration.

### 4.3 "Why this default?" explanations

For every default value the agent proposes, the user sees:

- A one-sentence rationale ("Default soil class M assumed; typical for Melbourne suburban infill").
- The schedule impact of changing it ("Changing to Class P adds approximately 5–10 working days to substructure").
- A "Source" tag (library reference, regional default, or LLM inference flagged for review).

### 4.4 Unknown-handling

The user can mark any item as:

- **Unknown — use conservative assumption** (the agent applies a documented conservative default).
- **Unknown — flag as high risk** (the item is added to the Risk and Uncertainty Log with an explicit owner and required action).

### 4.5 Planning Basis Summary

Once the PIR is complete, the agent produces a **Planning Basis Summary** — a single-page structured document listing every assumption, default, source, and uncertainty. The user must explicitly approve this summary before the agent proceeds to WBS generation. This is the agent's contractual hand-shake with the user.

---

## 5. Scope of the Agent

The agent supports early-stage planning for:

- Detached houses.
- Townhouse and multiplex developments.
- Medium-density residential projects.
- Small commercial buildings.
- Warehouses.
- School extensions.
- Fit-out projects.
- Refurbishment projects.
- Small institutional or community facilities.

The initial scope remains focused on **preliminary planning at AACE Class 5–4 maturity**, not contract-ready scheduling.

---

## 6. Construction-Native Planning Logic

The agent is designed for construction project management, not manufacturing or job-shop scheduling.

A construction project is modelled as:

```text
Design + Approvals + Procurement + Site Execution + Commissioning + Handover + Defects
```

not merely as a chain of on-site activities. The planning logic accounts for:

- Pre-construction activities including design coordination and RFI cycles.
- Authority approvals, traffic management plans, OHS plans, EPA submissions, and out-of-hours permits.
- Enabling works and preliminaries.
- Site access, temporary works, laydown availability, and crane access windows.
- Work fronts and location zones.
- Trade sequencing and crew continuity.
- Authority inspections and hold points modelled as zero-duration milestones.
- Weather-sensitive activities.
- Procurement lead times including consultant review loops.
- Construction calendars, EBAs, RDOs, public holidays, and shutdowns.
- Commissioning, defects, occupancy, and handover requirements.

---

## 7. WBS Structure

### 7.1 Deliverable vs process separation

WBS is **deliverable-based** (what is being built), per PMBOK and ISO 21502. Process artefacts are tracked in parallel registers and linked into the WBS through dependencies. Specifically:

- **WBS** = deliverable hierarchy.
- **Activity list** = process decomposition under each WBS leaf.
- **Procurement schedule** = parallel artefact, linked into construction WBS via FS predecessors on installation activities.
- **Approvals register** = parallel artefact, linked similarly.
- **Inspection register** = parallel artefact, surfacing as zero-duration milestones.

### 7.2 Recommended hierarchy

```text
Level 1: Project phase or major deliverable group
Level 2: Location / zone / building area
Level 3: Trade or work package
Level 4: Activity
```

Typical Level 1 deliverable groupings include: Site Works and Earthworks, Substructure, Superstructure, Envelope and Façade, Services Rough-in, Internal Works and Finishes, External Works and Landscaping, Commissioning and Handover, Defects and Close-out. Process groups (Design and Documentation, Authorities and Approvals, Procurement) are tracked as parallel registers but presented in the same Excel workbook for convenience.

The agent must avoid flat WBS outputs. Location and trade tagging are mandatory because they support later resource loading, work-front analysis, location-based scheduling, and 4D BIM linkage.

---

## 8. Duration Estimation Philosophy

### 8.1 Production-rate logic

```text
Duration = Quantity ÷ (Production rate × Crew size × Calendar efficiency)
```

The LLM does not "guess" durations. It infers approximate quantities (using a typological library of building archetypes), retrieves production rates from a curated library, and combines them into duration estimates with full traceability.

### 8.2 Three-point durations from day one

The data model carries **optimistic / most-likely / pessimistic** durations from the first version. CPM runs on most-likely; the additional values support PERT, three-point estimating, and later Monte Carlo without schema migration.

### 8.3 AACE estimate class anchoring

Outputs are explicitly labelled by AACE estimate class (Recommended Practice 18R-97):

| Class | Project definition | Range | Typical use |
|---|---|---|---|
| 5 | 0–2% | −50% / +100% | Concept screening |
| 4 | 1–15% | −30% / +50% | Feasibility |
| 3 | 10–40% | −20% / +30% | Budget authorisation |
| 2 | 30–75% | −15% / +20% | Control baseline |
| 1 | 65–100% | −10% / +15% | Bid / definitive |

Phase 1 outputs are Class 5 or Class 4. Stating this explicitly defuses the "but is this accurate?" question because the range is published and accepted.

### 8.4 Required basis fields per duration

- Quantity, unit, and quantity source (user input, typological inference, or library lookup).
- Production rate, unit, low/typical/high range.
- Production-rate source (library reference or LLM inference flagged for review).
- Crew composition.
- Calendar basis.
- Weather or risk buffer if applied.
- Three-point duration values.
- Confidence level (mapped to AACE class).
- Human-review flag.

### 8.5 Project completion as a date range

The agent reports project completion as **P50 and P80 dates**, not a single number. Three-point durations and PERT/β-distribution formulas produce these without full Monte Carlo. Reporting "PC: 24 weeks (P50) to 31 weeks (P80)" is more honest and more useful than a single deterministic figure.

---

## 9. Knowledge Libraries

### 9.1 Start simple: static, version-controlled tables

For Phase 1, libraries are **static, version-controlled CSV or JSON files** curated by experienced planners. A full RAG/vector database is overkill until the core workflow is stable and historical schedules are available. RAG is introduced from Phase 3 onwards.

### 9.2 Library schemas

**Production-rate library**

| Column | Notes |
|---|---|
| ActivityType | e.g. "concrete_slab_on_ground" |
| Unit | m², m³, lm, no., etc. |
| TypicalRate | central estimate |
| LowRate / HighRate | for three-point durations |
| CrewComposition | text |
| Source | Rawlinsons, Cordell, AIQS, organisation data |
| LastUpdated | date |
| Notes | regional or methodological caveats |

**Construction-logic library**

| Column | Notes |
|---|---|
| RuleID | unique |
| Description | e.g. "Slab cure ≥ 7 days before frame loading" |
| AppliesToProjectTypes | list |
| Severity | Warning or Error |
| SuggestedFix | text |
| Source | NCC, AS reference, industry practice |

**Procurement lead-time library**

| Column | Notes |
|---|---|
| ItemCategory | e.g. "switchboard_commercial_400A" |
| TypicalWeeksMin / TypicalWeeksMax | ranges |
| RequiredPrecedents | design freeze, shop drawings, FAT, etc. |
| Source | text |
| LastUpdated | date |

**Calendar library**

Working calendars, public holidays, EBA/RDO patterns, Christmas shutdown windows, weather-day allowances by region and season. Include `VIC_5DAY_STANDARD_2026` as the default; regional overrides for Melbourne CBD vs outer growth corridors are supported.

**Building typology library**

Archetypes (e.g. "two-storey detached, double-brick, hipped roof, 250 m² GFA") with quantity ratios per square metre of GFA. Used for parametric quantity inference. Each output is flagged as a parametric estimate requiring planner confirmation.

**WBS template library**

Reusable WBS templates per project type, aligned to UniFormat II or OmniClass for structured classification.

### 9.3 Library-grounded LLM as a hard rule

Production rates, lead times, and construction-logic rules are **never invented** by the LLM. If a value is not in the library, the agent flags "not in library — planner input required." This is enforced through schema validation and prompt design.

---

## 10. Procurement Schedule as a Core Output

### 10.1 Inclusion from Phase 1

Procurement is a Phase 1 deliverable, not a Phase 5 enhancement. On most projects beyond simple detached houses, procurement drives the critical path.

### 10.2 Expanded procurement chain

The procurement sequence is modelled with discrete, trackable activities:

```text
Design freeze
→ Submit shop drawings
→ Consultant review (RFI loop)
→ Final approval
→ Sample / mock-up approval (where applicable)
→ Long-lead deposit / PO release
→ Fabrication / manufacture
→ Factory Acceptance Test (FAT) where applicable
→ Pre-delivery survey (laydown, crane access)
→ Delivery to site
→ Site Acceptance Test (SAT) where applicable
→ Installation
```

The "Consultant review (RFI loop)" step is split out explicitly because it is the most common cause of procurement schedule slippage and forces the planner to allocate realistic lag for external dependencies.

### 10.3 Linkage rule

Every long-lead installation activity in the construction schedule has a hard FS predecessor on its delivery activity. Any long-lead item without a linked installation activity is a validation **error**, not a warning.

---

## 11. Dependencies and Relationship Types

The schedule data model supports:

- FS, SS, FF, SF relationships.
- Lags and leads (positive and negative).
- Cure periods, inspection holds, and external authority constraints modelled as explicit lags or zero-duration milestones, never hidden inside activity durations.
- Procurement predecessors and milestone constraints.

Inspection and approval gates (frame inspection, waterproofing PIC inspection, Practical Completion, Certificate of Occupancy, statutory authority sign-offs) are modelled as **zero-duration milestone activities** with constraints, so they appear visibly on the bar chart and are trackable for AS 4000 contract administration.

---

## 12. Calendar and Regional Logic

The CPM engine uses working calendars, not simple day counts. For Australian and Victorian construction contexts:

- 5-day, 5.5-day, or 6-day working weeks.
- Victorian public holidays (11 days plus AFL Grand Final eve).
- Industry RDO rosters where applicable (typically 1 in 20 working days under CFMEU EBAs on commercial sites).
- Christmas/New Year shutdown (typically 21 December – 14 January).
- Weather assumptions differentiated by location: Melbourne CBD (lower rain days) vs outer growth corridors and Geelong/regional Victoria (higher).
- Site working-hour and noise restrictions.
- Residential vs commercial work patterns.

The default calendar is `VIC_5DAY_STANDARD_2026`. Project-specific overrides are supported. Implementation uses pandas business day offsets, python-dateutil, or a custom calendar class — whichever cleanly supports compound calendars (working days + weather days + RDOs + shutdowns).

---

## 13. Human-in-the-Loop Workflow

### 13.1 Mandatory review checkpoints

Two mandatory checkpoints:

1. **Planning Basis Approval** — after PIR, before WBS generation.
2. **Draft Schedule Review** — after WBS, activities, and durations are generated, before CPM is calculated.

### 13.2 Edit modality

The user can edit through:

- A structured table interface (preferred for bulk edits).
- A conversational interface for individual changes ("change slab cure lag to 10 days").
- Excel round-trip (download, edit, re-upload, agent re-validates).

### 13.3 Edit logging

All edits are logged with:

- Timestamp.
- Author identity.
- Field changed (old value → new value).
- Reason (free text, optional).

### 13.4 Agent push-back on illogical edits

When a user edit conflicts with a construction-logic rule (e.g. removing slab cure lag, plastering before frame inspection), the agent flags but does not block. The user can override with explicit acknowledgement, and the override is recorded in the audit trail.

### 13.5 Lock-on-Baseline

Once a Baseline schedule is set, edits to predecessor logic and durations are tracked as variance, not silent overwrites. This is essential for any later delay analysis or EOT claim work.

---

## 14. Role of the LLM

The LLM handles interpretive and narrative tasks:

- Interpreting the brief project description.
- Generating the conversational PIR.
- Inferring missing scope where necessary, with explicit flags.
- Selecting an appropriate WBS template from the library.
- Identifying likely activities and work packages within library constraints.
- Suggesting which production-rate entries apply.
- Explaining assumptions and uncertainty.
- Drafting the Planning Basis Summary.
- Drafting the Basis of Schedule narrative.
- Drafting the schedule narrative, assumptions register, and risk register.

The LLM is **not** responsible for CPM calculations, float calculations, date calculations, calendar arithmetic, or resource optimisation.

---

## 15. Role of Code

The code layer handles deterministic, auditable tasks:

- Schema validation (Pydantic).
- Activity ID and reference integrity checks.
- Predecessor/successor closure checks.
- Circular dependency detection.
- Construction-logic rule application.
- Calendar arithmetic and working-day conversions.
- CPM forward and backward pass; ES, EF, LS, LF, total float, free float.
- Schedule-quality checks (DCMA-style, adapted).
- Procurement-to-installation link enforcement.
- Excel and chart generation.
- Version history and change logging.

Any LLM output failing schema validation is **rejected and re-prompted**, never silently coerced.

---

## 16. Construction-Aware Validation

### 16.1 Rule categories

The validation engine implements rules across:

**Logical sequencing**
- Substructure before superstructure.
- Slab cure lag before frame loading.
- Frame inspection before internal linings.
- Roof and envelope before moisture-sensitive internal finishes.
- Services rough-in before plasterboard.
- Waterproofing inspection before tiling in wet areas.
- Render cure before painting.
- Final electrical certification before occupancy.
- Practical Completion inspection before handover.

**Schedule quality (DCMA-style, adapted for construction)**
- Open-ended activities (no predecessor or successor).
- Excessive negative float.
- Excessive positive float (>50 days flagged for review).
- Long-duration activities (>25 working days without breakdown or hammock flag).
- Large lag values without justification.
- Hard constraints that override logic.
- Missing start/finish milestones.

**Construction-specific**
- Missing enabling works or preliminaries.
- Missing design, approvals, or procurement activities.
- Missing authority inspections.
- Missing weatherproofing before moisture-sensitive internal works.
- Missing waterproofing inspection before tiling.
- Missing final inspection before handover.
- Missing commissioning sub-activities (pre-com, integrated systems testing, witness testing).

**Crew continuity and constructability**
- Same-trade activities fragmented across more than 3 non-contiguous periods (loss of learning curve and mobilisation cost).
- Tower crane in preliminaries without a corresponding crane dismantle activity sequenced after heavy superstructure/envelope works.
- Scaffold erection without corresponding scaffold dismantle.
- Site shed establishment without corresponding demobilisation.

**Weather and seasonal**
- External works (roofing, cladding, landscaping, external paint) scheduled in Melbourne winter without ≥15% weather contingency.
- Concrete pours scheduled on extreme-heat days without protection allowance.

**Procurement integrity**
- Long-lead item without linked installation activity (Error).
- Installation activity without linked procurement chain (Error).
- Consultant review duration <5 working days (Warning).

**Staged handover**
- Multi-stage projects without separate PC milestone and defects period per stage.

**Quantity and rate sanity**
- Concrete pour >500 m³/day without justification.
- Production rate outside library low/high range without override flag.

### 16.2 Severity model

Each rule carries a severity (Error / Warning / Info). Errors block schedule export until resolved or explicitly overridden with reason. Warnings appear in the Validation Warnings tab. Info entries appear in the planner review checklist.

---

## 17. CPM, Location-Based Scheduling, and Resource Logic

CPM is necessary but not sufficient. It is the contractual and baseline planning view, used widely for contract programmes, progress monitoring, and AS 4000 EOT analysis. However, CPM assumes unlimited resources and does not naturally handle trade continuity, work fronts, or repetitive construction.

The agent therefore:

- Produces calendar-aware CPM as the primary output.
- Surfaces resource awareness from Phase 3 (indicative crews, peak manpower, simple over-allocation warnings).
- Adds location-based scheduling, Line of Balance, or Takt-style views for repetitive projects (Phase 4).
- Uses construction-aware heuristics rather than generic mathematical optimisation for resource levelling.

Resource-constrained scheduling (RCPSP) is NP-hard at scale; exact optimisation is not suitable for large schedules. The agent supports heuristic and planner-guided levelling.

Last Planner System vocabulary — constraints, commitments, look-ahead, percent plan complete — informs the validation engine even in early phases. A warning like *"Activity A120 has 3 unresolved constraints (procurement, design, access)"* is more actionable than a generic "human review required" flag.

---

## 18. Activity Data Structure

Each activity carries the following fields. Fields nullable in Phase 1 are stubbed in the schema to avoid migration later.

```json
{
  "activity_id": "A120",
  "wbs_code": "7.2.1",
  "wbs_parent_id": "7.2",
  "wbs_name": "Substructure / Ground Floor / Concrete",
  "wbs_dictionary_ref": "WBS-7.2.1",
  "activity_name": "Construct ground floor slab",
  "activity_type": "construction",
  "location_zone": "Ground floor - main building footprint",
  "spatial_guid": null,
  "ifc_element_id": null,
  "trade": "Concrete",
  "responsible_party": "Head Contractor",
  "quantity": 180,
  "unit": "m2",
  "quantity_source": "Typological inference - 250m2 GFA detached, ratio 0.72",
  "production_rate": 40,
  "production_rate_unit": "m2/day",
  "production_rate_low": 30,
  "production_rate_high": 55,
  "production_rate_source": "Library: concrete_slab_on_ground_v2026.1",
  "crew_composition": "1 concrete crew; 4 workers; concrete pump",
  "duration_optimistic_days": 4,
  "duration_most_likely_days": 5,
  "duration_pessimistic_days": 8,
  "calendar_id": "VIC_5DAY_STANDARD_2026",
  "calendar_efficiency_factor": 0.85,
  "predecessors": [
    {
      "activity_id": "A110",
      "relationship_type": "FS",
      "lag_days": 0,
      "lag_reason": null
    }
  ],
  "successors": [
    {
      "activity_id": "A130",
      "relationship_type": "FS",
      "lag_days": 7,
      "lag_reason": "Slab cure before frame loading (NCC; AS 3600)"
    }
  ],
  "permit_required": false,
  "inspection_hold": true,
  "inspection_milestone_id": "M-INSP-005",
  "weather_sensitive": false,
  "procurement_item": false,
  "procurement_chain_ref": null,
  "lead_time_weeks": null,
  "buffer_days": 0,
  "risk_weighting": "Medium",
  "confidence_level": "AACE Class 5",
  "human_review_required": true,
  "budgeted_cost": null,
  "cost_loading_rule": null,
  "assumption": "Standard slab-on-ground; soil class M assumed (default for Melbourne suburban infill); requires planner confirmation.",
  "audit": {
    "generated_by": "agent_v1.0",
    "generated_at": "2026-05-03T10:00:00+10:00",
    "edited_by": null,
    "edited_at": null
  }
}
```

The `spatial_guid` and `ifc_element_id` fields are intentionally included and nullable. Retrofitting BIM linkage later would require a database overhaul; carrying the fields from day one makes future 4D BIM integration trivial.

The cost fields (`budgeted_cost`, `cost_loading_rule`) similarly enable Phase 3 cash-flow integration without schema migration.

---

## 19. Professional Output Package

A credible preliminary planning package includes:

1. Executive summary with P50/P80 completion dates.
2. Project interpretation.
3. Planning Basis Summary (the user-approved version).
4. Basis of Schedule narrative.
5. WBS and WBS dictionary.
6. Full activity schedule with three-point durations.
7. CPM results (ES, EF, LS, LF, float, criticality).
8. Critical path narrative.
9. Procurement schedule and long-lead item register.
10. Approvals and inspections register.
11. Assumptions register.
12. Risk and Uncertainty Log with activity linkage.
13. Resource register and indicative peak manpower (Phase 3+).
14. Indicative cash-flow curve (Phase 3+).
15. Calendar and working-time assumptions.
16. Validation warnings and schedule-quality report.
17. Planner review checklist and sign-off section.
18. Excel workbook export.
19. PDF report (Phase 5).
20. MS Project XML or Primavera-compatible export (Phase 5).

### 19.1 Planner Sign-Off section

A dedicated tab/section requires the planner to confirm:

- All high-uncertainty items reviewed and confirmed or adjusted.
- Procurement lead times cross-checked with current supplier quotes.
- Weather and calendar assumptions accepted for the project location and season.
- Validation warnings reviewed and either accepted or mitigated.
- Basis of Schedule narrative reviewed for accuracy.
- Planner name, professional registration, date, and signature line (digital).

The package is not considered final until this section is completed.

---

## 20. Excel Workbook Structure

### 20.1 Phase 1 — 8 tabs (minimum viable professional package)

1. **Executive Summary** — project interpretation, P50/P80 completion, AACE class, top risks, major assumptions, review status.
2. **Project Information Request** — confirmed/unknown variables, defaults applied, why-this-default rationale.
3. **Basis of Schedule** — methodology, scope basis, calendar, productivity basis, exclusions, limitations.
4. **WBS and Dictionary** — WBS element, definition, inclusions, exclusions, deliverables, confidence level.
5. **Full Schedule** — activity ID, WBS, name, three-point durations, calendar, predecessors, successors, trade, location, resources, assumptions, confidence.
6. **Procurement Schedule** — long-lead items with full chain (design freeze through installation).
7. **Assumptions and Risk Register** — combined for Phase 1 simplicity.
8. **Validation Warnings and Sign-Off** — schedule-quality results plus the planner sign-off checklist.

### 20.2 Phase 2 — expand to 12 tabs

Add:

9. **Milestone Register** — client milestones, authority inspections, PC, handover, defects commencement.
10. **Resource Register** — indicative crews, plant, peak manpower, resource-constrained warnings.
11. **Change Log** — human edits, timestamps, author, reason.
12. **Critical Path Narrative** — annotated.

---

## 21. Technical Architecture

### 21.1 Logical architecture

```text
User input (form or PDF upload)
→ LLM: project interpretation and PIR generation
→ User: confirms PIR, approves Planning Basis Summary
→ LLM: WBS, activities, procurement items, parametric quantities
→ Library lookups: production rates, logic rules, lead times, calendars
→ LLM: structured JSON draft (Pydantic-validated)
→ Human review checkpoint
→ Code: construction-logic and schedule-quality validation
→ Code: calendar-aware CPM
→ Code: Excel workbook generation
→ LLM: Basis of Schedule and narrative
→ Planner sign-off
→ Editable planning package issued
```

### 21.2 n8n workflow

```text
Form Trigger
→ Capture project brief and location
→ LLM Node: PIR generation
→ Human input/approval step (Planning Basis)
→ LLM Node: WBS and activity JSON
→ Code Node: library lookups
→ Code Node: Pydantic schema validation
→ Code Node: construction rule checks
→ Code Node: calendar-aware CPM
→ Spreadsheet File Node: 8-tab Excel workbook
→ LLM Node: Basis of Schedule and narrative
→ Human input: planner sign-off
→ Respond with file and review notes
```

### 21.3 Model selection strategy

Multi-call agents can be token-expensive. Model assignment per call:

- **Strongest model** (e.g. Claude Opus): project interpretation, PIR generation, Basis of Schedule narrative.
- **Mid-tier model** (e.g. Claude Sonnet): WBS and activity generation, validation explanation.
- **Cheaper/faster model** (e.g. Claude Haiku): Pydantic re-prompt loops, formatting, simple narrative inserts.
- **No LLM**: library lookups, CPM calculation, calendar arithmetic, Excel generation.

---

## 22. Recommended Libraries and Tools

| Purpose | Tool |
|---|---|
| Structured data handling | pandas |
| Excel generation | openpyxl |
| Dependency graph | NetworkX |
| CPM calculation | Custom Python, calendar-aware |
| Calendar handling | pandas business day offsets, python-dateutil, custom class |
| JSON/schema validation | Pydantic |
| Rule engine | Custom Python rules, optionally durable rules |
| RAG/retrieval (Phase 3+) | Vector DB plus structured lookup |
| Optimisation/levelling | OR-Tools, PuLP, Pyomo, or construction heuristics |
| Gantt/charts | Plotly or matplotlib |
| Workflow automation | n8n |
| LLM API | OpenAI, Gemini, or Claude |

Phase 1 stack:

```text
LLM API + structured JSON + Pydantic + static CSV/JSON libraries + custom calendar-aware CPM + pandas/openpyxl Excel export + n8n orchestration
```

---

## 23. Phased Development Plan

### Phase 1a — Foundation (Weeks 1–6)

- Conversational PIR with structured form output and "why this default?" explanations.
- Planning Basis Summary and explicit user approval gate.
- Project-type classification and Melbourne/Victoria-aware defaults.
- Static CSV/JSON libraries for production rates, logic rules, lead times, calendar, and building typologies.
- Hybrid WBS (Phase + Location + Trade) with 4-level depth.
- Activity list with three-point production-rate-derived durations.
- Procurement schedule for long-lead items with full chain modelled.
- Basic calendar engine (5-day + VIC public holidays + RDO + Christmas shutdown).
- 10–12 core construction validation rules.
- Human review checkpoint with edit logging.
- 8-tab Excel workbook plus professional disclaimer.
- AACE Class 5/4 labelling on outputs.
- Planner Sign-Off checklist.

### Phase 1b — CPM and Polish (Weeks 7–10)

- Calendar-aware CPM with three-point durations (most-likely for forward/backward pass, range for P50/P80).
- Float calculation and critical path identification.
- LLM-generated, human-editable critical path narrative.
- Expanded validation warnings (full DCMA-style + construction-specific list).
- Basis of Schedule narrative.
- Risk and Uncertainty Log with activity linkage.
- Lock-on-Baseline behaviour.

### Phase 1c — Calibration (Weeks 11–14)

- Run agent against 5–8 anonymised historical projects from different planners.
- Measure: edit rate to make draft usable, rate vs as-built duration deltas, validation true-positive rate, planner satisfaction (1–10) on transparency and auditability.
- Iterate libraries and rules based on findings.
- Publish calibration report as the empirical evidence base for the agent.

### Phase 2 — Resource Awareness and Expanded Outputs

- Indicative crew sizes, plant, equipment.
- Peak manpower estimates and resource histogram.
- Simple resource-constrained warnings (no full levelling).
- Trade fragmentation and constructability flags expanded.
- 12-tab Excel workbook (add Milestone Register, Resource Register, Change Log, Critical Path Narrative tabs).
- Indicative cash-flow curve (high-level unit rates × quantities).
- PDF report generation.

### Phase 3 — Resource Levelling and RAG

- Construction-aware heuristic resource levelling.
- Scenario comparison (e.g. 5-day vs 6-day calendar, accelerated vs as-planned).
- Work-front continuity checks expanded.
- RAG layer over historical schedules and curated documents.
- Optional cost loading and EVA hooks (AS 4817 alignment).

### Phase 4 — Location-Based and Repetitive Project Support

- Location-based scheduling view.
- Line of Balance and Takt outputs for repetitive projects.
- Trade flow-line visualisation.

### Phase 5 — Advanced Outputs and Integration

- MS Project XML export.
- Primavera-compatible export where feasible.
- Baseline vs Current vs As-built comparison.
- Monte Carlo schedule-risk simulation.
- 4D BIM linkage hooks (using `spatial_guid` / `ifc_element_id` already in schema).
- Full Last Planner System integration (look-ahead, commitment tracking, PPC).

---

## 24. Versioning and Schedule States

The agent supports schedule versioning from Phase 1:

- Target schedule.
- Baseline schedule (locked).
- Current schedule.
- Revised schedule.
- As-built schedule (Phase 5).

A delta narrative is generated on each version change explaining what shifted, by how much, and why. Lock-on-Baseline ensures all subsequent edits are tracked as variance, not silent overwrites.

---

## 25. Standards and Practice Alignment

- **PMBOK Guide** and **ISO 21502 / ISO 21500** for project management vocabulary.
- **AACE International RP 18R-97** for estimate class labelling.
- **AS 4817** for project performance measurement using EVA (Phase 3+).
- **AS 4000 / AS 2124** contract administration vocabulary for delay analysis.
- **AS 2870** for soil class references.
- **AS 3600** (concrete), **AS 1684** (timber framing), **AS 3500** (plumbing), **AS 3000** (electrical), **AS 1851** (fire systems), **AS 5601** (gas) for inspection and commissioning gates.
- **NCC** for regulatory and approval gates.
- **NATSPEC** for trade and specification structure.
- **AIPM** practice standards.
- **UniFormat II** or **OmniClass** for WBS classification.
- **DCMA 14-Point Schedule Assessment** adapted for construction.
- **Location-Based Management System / Line of Balance / Takt** literature for repetitive projects.
- **Last Planner System** principles for execution-level planning.

---

## 26. Evaluation and Calibration Strategy

The agent is designed to be empirically defensible. The Phase 1c calibration phase, supplemented by ongoing benchmarking, includes:

### 26.1 Quantitative metrics

- **Edit rate**: percentage of agent-generated activities requiring human edit before draft is usable. Target <30% for residential, <40% for small commercial.
- **Duration accuracy**: median and IQR of (agent most-likely duration − as-built duration) ÷ as-built duration. Target P50 within ±25% (consistent with AACE Class 4).
- **Validation true-positive rate**: percentage of validation warnings corresponding to real schedule issues observed on the calibration projects.
- **DCMA score**: overall percentage on the 14-point check.
- **Time-to-first-draft reduction**: paired study with planners using vs not using the agent.

### 26.2 Qualitative metrics

- Planner satisfaction (1–10) on transparency, auditability, trustworthiness.
- Inter-rater comparison: same brief given to 3–5 planners and the agent; compare WBS coverage, activity count, duration distribution, critical path identity, validation completeness.

### 26.3 Publication potential

This evaluation methodology supports submission to:

- **Journal of Computing in Civil Engineering (JCCE)**.
- **Engineering, Construction and Architectural Management (ECAM)**.
- **Automation in Construction**.
- **Construction Management and Economics**.

---

## 27. Professional Disclaimer

Each output includes:

> This schedule is a preliminary planning output (AACE Class 5 or Class 4) generated from limited project information. Durations, sequencing, procurement assumptions, resources, calendars, and risks are indicative only. The output is not contractually reliable and must not be appended to tender documents, contracts, or site-execution instructions without review, correction, and approval by an appropriately qualified and insured construction planner, project manager, or superintendent. Quantities marked as parametric or typologically inferred require independent verification before any cost or duration commitment.

---

## 28. Key Design Principles

The agent always distinguishes between:

- Information explicitly provided by the user.
- Information inferred by the LLM (flagged for review).
- Information retrieved from named, version-controlled libraries.
- Defaults applied where information is missing.
- Human-reviewed and confirmed inputs.
- Calculated results produced by code.

Every duration, dependency, and assumption is traceable to one of these sources. The output is designed to make uncertainty **visible**, not hidden behind a polished Gantt chart.

Library values are authoritative over LLM inference. Where the library has no entry, the agent flags "not in library — planner input required" rather than inventing a value.

---

## 29. Summary

The agent is positioned as a **construction planner's assistant** that supports first-draft planning from incomplete project briefs. Its value lies in:

- Asking the right questions through a conversational, progressively disclosed PIR.
- Grounding durations in production-rate logic and three-point AACE-class estimates.
- Validating construction sequencing through a curated, construction-aware rule set.
- Treating procurement as a Phase 1 deliverable, not an afterthought.
- Producing an auditable, multi-tab Excel package with explicit assumptions, risks, and a planner sign-off section.

The defensible framing is:

> AI scaffolds and accelerates the planner's first draft, while surfacing assumptions, uncertainty, productivity logic, procurement constraints, calendar effects, construction-sequence risks, and constructability concerns for human review.

The immediate development priority is the **minimum viable professional package** delivered in 10–14 weeks (Phase 1a + 1b + 1c):

```text
Conversational PIR with Planning Basis approval gate
+ Hybrid WBS and activity generation grounded in static libraries
+ Three-point production-rate-based durations
+ Procurement schedule with full chain (including consultant review)
+ Calendar-aware CPM
+ 10–12 core construction validation rules expanding to full DCMA-style set
+ Basis of Schedule narrative
+ 8-tab Excel workbook with Planner Sign-Off
+ Calibration against 5–8 historical projects
```

This delivers a rock-solid, transparent first draft that experienced planners will trust and adopt — which is more valuable than a flashy but incomplete "full schedule." Everything else follows in disciplined, evidence-led increments.

---

## Appendix A — Document History

| Version | Date | Notes |
|---|---|---|
| 0.1 | Initial concept | Original intention and plan; identified core idea but framed as autonomous schedule generator. |
| 0.2 | First revision | Reframed as human-in-the-loop assistant; added PIR, production-rate philosophy, procurement as core, multi-tab Excel, standards alignment. |
| 1.0 (this document) | 3 May 2026 | Final consolidated plan. Adds: conversational/progressive PIR, AACE estimate class anchoring, three-point durations from day one, hold points as zero-duration milestones, library-grounded LLM as a hard rule, expanded procurement chain (consultant review split, FAT/SAT, sample approval), spatial_guid/ifc_element_id and cost fields stubbed in schema, expanded validation (crew continuity, weather buffer, staged handover, constructability flags), Phase 1a/1b/1c structure with calibration phase, Planner Sign-Off section, evaluation methodology for academic publication, model selection strategy. |
