# Development Journey: Construction Planning & Scheduling Agent

This document tracks the evolution of the Construction Planning Agent from its initial conception to its current implementation. It is intended for students and researchers to understand the "thinking" and "expert feedback" that shaped the application's architecture.

---

## 🏗️ Phase 1: Conceptualization & Initial Architecture

### 1. The Core Idea
The project started with a fundamental technical question: *Can we create an LLM-based system that uses API calls or deterministic code during the workflow?*

**The Strategy:**
- **LLM Reasoning:** Interprets the brief and decides on tool usage.
- **Code Execution:** Handles calculations (CPM, validation).
- **LLM Synthesis:** Writes the final professional report.

### 2. Identifying the Stack
We initially looked at general scheduling libraries (OR-Tools, PuLP, etc.).
**Key realization:** Construction projects are NOT manufacturing "job-shops". They require location-based logic, trade sequencing, and procurement lead times.

### 3. Defining the Workflow
The agent was designed to start from a "thin" project description (e.g., "Two-storey house in Melbourne") and infer the rest.

---

## 📝 Phase 2: Initial Plan & Expert Critique

### The Initial Document
File: `docs/planning/construction_planning_agent_intention_and_plan.md` (Archived)

### 🔴 Expert Review: Stage 1 (Grok & Gemini)
*Feedback received on the first conceptual draft.*

**Grok's Critique:**
- **Too Optimistic:** LLMs cannot "guess" durations accurately.
- **Missing Regulatory Logic:** Victorian construction needs Building Permits and VBA inspections.
- **Soil Matters:** "Slab-on-ground" assumptions are dangerous without geotech context.
- **Recommendation:** Ground durations in productivity data (e.g., Rawlinsons).

**Gemini's Critique:**
- **Data Architecture:** Use RAG (Retrieval-Augmented Generation) for historical benchmarks.
- **Pre-Construction Gap:** The schedule must include Design, Approvals, and Procurement (DAP) phases.
- **Human-in-the-Loop:** Don't go straight to output; let the planner review the JSON activities first.

---

## 🔄 Phase 3: Major Revision & Refinement

### The Revised Strategy
Based on the Stage 1 feedback, the project was pivoted from "AI generates schedule" to "AI scaffolds a planner's first draft."

### 🟢 Expert Review: Stage 2 (Revised Plan)
*Feedback on the revised framework (PIR + Production-Rate logic).*

**Grok's Critique:**
- **PIR is King:** The "Project Information Request" is the most important new feature.
- **Deterministic Cross-checks:** Verified the move to arithmetic-based durations.
- **Recommendation:** Keep the Phase 1 release "Minimum Viable Professional" (MVP).

**Gemini's Critique:**
- **Conversational Elicitation:** The PIR shouldn't be a static form; it should be an LLM-driven dialogue.
- **Spatial Anchoring:** Prepare the data structure for future 4D BIM integration.

---

## 🚀 Phase 4: Implementation & App Architecture

### Choice of Platform
We evaluated n8n, Firebase, and Custom Python.
**Selected Approach:** Gemini API + Streamlit + Python Scheduling Engine.

### Final Design Decisions
- **Separation of Concerns:** `llm_service.py` handles the "soft" reasoning; `page_04_schedule.py` handles the "hard" CPM math.
- **Location Awareness:** Hardcoded awareness of Melbourne/Victorian RDOs and public holidays.
- **Basis of Schedule:** Automatically generating the professional narrative that explains *why* the schedule looks the way it does.

---

## 🛠️ Reference: Original Expert Comments

### Grok - Stage 1 (On Original Plan)
> "Construction is not manufacturing. Every site has unique geotechnical, regulatory, weather, and access constraints... The agent must be deliberately conservative and brutally transparent about uncertainty."

### Grok - Stage 2 (On Revised Plan)
> "The shift to a human-in-the-loop planning assistant that first issues a PIR is exactly the right direction. This makes the tool defensible to professional planners."

### Gemini - Combined Critique
> "Planners do not trust black boxes... Highlight the consultant review period explicitly... Multi-stage projects need distinct PC milestones."

---
*Document Version: 1.0 (May 2026)*
