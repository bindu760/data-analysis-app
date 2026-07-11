# AI Data Analyst & Reporter (Streamlit)

CSV / Excel / JSON upload → plain-language question → AI-generated pandas/matplotlib
code → runs inside an **E2B sandbox** → charts → an AI **Reporter Agent** writes a
narrative → everything is packaged into a **PDF report**.
The Code Agent, Sandbox, and Reporter Agent steps are orchestrated as an explicit **LangGraph** graph (`graph.py`).

## Flow

1. User uploads a data file (`.csv`, `.xlsx`, `.xls`, `.json`).
2. User types a question in plain English/Nepali about the data.
3. **Code Agent** (Groq / Llama) reads the data's schema + the question, and writes a
   complete pandas + matplotlib analysis script. *(This is Node 1 of the LangGraph graph.)*
4. That script is shipped into an **E2B Code Interpreter sandbox** and executed
   there (isolated, safe — never runs on your own machine).
5. Any chart images and printed findings come back from the sandbox. *(Node 2 of the graph.)*
6. **Reporter Agent** (Groq / Llama) turns those findings into a clean, structured
   narrative (Executive Summary, Key Findings, Chart Insights, Recommendations,
   Conclusion). *(Node 3 of the graph.)*
7. `pdf_report.py` (ReportLab) assembles the narrative + data preview + every
   chart into one polished, standard PDF — downloadable straight from the app.

## Setup

```bash
cd data-analysis-app
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You need two API keys:

| Key | Where to get it |
|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys |
| `E2B_API_KEY` | https://e2b.dev |

You can either:
- paste them directly into the sidebar fields when the app runs, **or**
- set them as environment variables before launching:

```bash
export GROQ_API_KEY="gsk_..."
export E2B_API_KEY="e2b_..."
```

## Run

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## File overview

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI — upload, query box, workflow orchestration, styling |
| `agents.py` | Code Agent + Reporter Agent (Groq / Llama calls) |
| `graph.py` | LangGraph `StateGraph` wiring: code_agent → sandbox → reporter_agent |
| `sandbox_executor.py` | Ships the dataframe + generated code into an E2B sandbox and runs it |
| `pdf_report.py` | Builds the final PDF (ReportLab): narrative + data table + charts |
| `requirements.txt` | Python dependencies |

## Security note

The generated analysis code always runs inside the E2B sandbox, never inside
your Streamlit server or browser — so even if the AI writes something odd,
your own machine and data stay isolated.