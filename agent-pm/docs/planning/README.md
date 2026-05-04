# Construction Planning Agent

An LLM-powered construction planning assistant that converts a brief project description into an auditable, editable, preliminary planning package for human review.

## Features

- **Conversational Project Information Request (PIR)**: Progressively asks questions to clarify scope, site constraints, and assumptions.
- **Library-Grounded Durations**: Durations are derived from production rates in a curated library, not "guessed" by the LLM.
- **Calendar-Aware CPM**: Calculates critical path, float, and completion dates using Victorian construction calendars.
- **Construction-Native Validation**: Checks for logical sequencing (e.g., slab cure before frame) and schedule quality (DCMA-style).
- **Professional Excel Output**: Generates an 8-tab workbook with WBS, Full Schedule, Procurement Register, and more.
- **Knowledge Base Management**: Users can upload their own production rates and logic rules.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Key**:
   - Create a `.env` file from `.env.example`.
   - Add your `GEMINI_API_KEY` (Gemini 3.1 Pro recommended).
   - Alternatively, you can enter the API key in the app sidebar.

3. **Run the App**:
   ```bash
   streamlit run app/main.py
   ```

## Usage for Students (ABPL90331)

1. **Step 1: Project Brief**: Enter a description of your project (or use an example).
2. **Step 2: Information Request**: Answer the agent's questions about your project.
3. **Step 3: Planning Basis**: Review and approve the assumptions made by the agent.
4. **Step 4: Schedule**: Review the generated WBS and activities. Edit as needed and calculate the CPM.
5. **Step 5: Export**: Review the critical path narrative and download your Excel Planning Package.

## Technology Stack

- **Frontend**: Streamlit
- **LLM**: Gemini 3.1 Pro (via google-genai)
- **Logic**: Python (Pandas, NetworkX, Pydantic, Openpyxl)
