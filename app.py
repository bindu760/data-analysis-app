"""
app.py - AI Data Analyst & Reporter

Upload a CSV / Excel / JSON file -> ask a question in plain language ->
  1) Code Agent (Claude) writes a pandas + matplotlib analysis script
  2) The script runs safely inside an E2B cloud sandbox
  3) Charts + text findings come back
  4) Reporter Agent (Claude) writes a clean narrative report
  5) Everything is packaged into a polished, downloadable PDF
"""

import io
import os
import json
import tempfile

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from graph import run_pipeline
from pdf_report import build_pdf_report

# Load variables from a local .env file (if present) into os.environ,
# e.g. GROQ_API_KEY=... / E2B_API_KEY=...
load_dotenv()

# ----------------------------------------------------------------------------
# Page config + styling
# ----------------------------------------------------------------------------
st.set_page_config(page_title="AI Data Analyst & Reporter", page_icon="📊", layout="wide")

CUSTOM_CSS = """
<style>
.main { background: linear-gradient(180deg, #f7f9fc 0%, #eef1f8 100%); }
.block-container { padding-top: 2rem; }

.hero {
    background: linear-gradient(120deg, #1f3864 0%, #2f5aa8 60%, #3f7fd6 100%);
    padding: 2.2rem 2.4rem;
    border-radius: 18px;
    color: white;
    margin-bottom: 1.6rem;
    box-shadow: 0 10px 30px rgba(31,56,100,0.25);
}
.hero h1 { margin: 0 0 6px 0; font-size: 2.1rem; }
.hero p { margin: 0; opacity: 0.9; font-size: 1.02rem; }

.step-card {
    background: white;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    box-shadow: 0 4px 16px rgba(20,30,60,0.06);
    border: 1px solid #eef0f5;
    margin-bottom: 1rem;
}
.step-badge {
    display: inline-block;
    background: #1f3864;
    color: white;
    border-radius: 999px;
    padding: 2px 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 6px;
}
div.stButton > button {
    background: linear-gradient(120deg, #1f3864, #3f7fd6);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.6rem 1.4rem;
    font-weight: 600;
}
div.stDownloadButton > button {
    background: linear-gradient(120deg, #1f6f43, #2ea862);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="hero">
        <h1>📊 AI Data Analyst &amp; Reporter</h1>
        <p>Upload CSV / Excel / JSON &rarr; ask a question in plain language &rarr;
        AI writes analysis code &rarr; runs it in an isolated E2B sandbox &rarr;
        get charts + a polished PDF report, automatically.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar - configuration
# ----------------------------------------------------------------------------
st.sidebar.header("🔑 Configuration")


def _get_key(name: str) -> str:
    """Check st.secrets first (persists across restarts), then env vars."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, "")


groq_key_saved = _get_key("GROQ_API_KEY")
e2b_key_saved = _get_key("E2B_API_KEY")

if groq_key_saved and e2b_key_saved:
    groq_key = groq_key_saved
    e2b_key = e2b_key_saved
    with st.sidebar.expander("Change keys for this session"):
        groq_key = st.text_input("Groq API Key", type="password", value=groq_key_saved)
        e2b_key = st.text_input("E2B API Key", type="password", value=e2b_key_saved)
else:
    st.sidebar.info(
        "💡 Tip: save your keys in `.streamlit/secrets.toml` so you never "
        "have to paste them again. See README for the exact format."
    )
    groq_key = st.sidebar.text_input(
        "Groq API Key", type="password",
        help="Get one free at console.groq.com/keys",
    )
    e2b_key = st.sidebar.text_input(
        "E2B API Key", type="password",
        help="Get one at e2b.dev",
    )
report_lang = st.sidebar.selectbox("Report language", ["English", "Nepali"])
st.sidebar.caption("Keys are only used for this session and are never stored.")

# ----------------------------------------------------------------------------
# File upload + parsing
# ----------------------------------------------------------------------------
uploaded_file = st.file_uploader(
    "📁 Upload your data file", type=["csv", "xlsx", "xls", "json"],
)


def load_dataframe(file) -> pd.DataFrame:
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    if name.endswith(".json"):
        raw = json.load(file)
        if isinstance(raw, list):
            return pd.json_normalize(raw)
        if isinstance(raw, dict):
            # try common shapes: {"data": [...]}, or a flat dict of columns
            for key in ("data", "records", "rows"):
                if key in raw and isinstance(raw[key], list):
                    return pd.json_normalize(raw[key])
            return pd.json_normalize(raw)
        raise ValueError("Unsupported JSON structure.")
    raise ValueError("Unsupported file type.")


if uploaded_file is not None:
    try:
        df = load_dataframe(uploaded_file)
        st.session_state["df"] = df
        st.session_state["filename"] = uploaded_file.name
    except Exception as e:
        st.error(f"Could not read this file: {e}")

# ----------------------------------------------------------------------------
# Main workflow
# ----------------------------------------------------------------------------
if "df" in st.session_state:
    df = st.session_state["df"]

    st.markdown('<div class="step-card"><span class="step-badge">STEP 1</span>', unsafe_allow_html=True)
    st.subheader(f"Data Preview — {st.session_state.get('filename','')}")
    st.dataframe(df.head(20), use_container_width=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", f"{df.shape[0]:,}")
    c2.metric("Columns", df.shape[1])
    c3.metric("Missing values", int(df.isna().sum().sum()))
    with st.expander("Column types"):
        st.write(df.dtypes.astype(str))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="step-card"><span class="step-badge">STEP 2</span>', unsafe_allow_html=True)
    st.subheader("Ask a question about your data")
    query = st.text_area(
        "What would you like to know?",
        placeholder="e.g. Show the monthly sales trend and the top 5 products by revenue",
        label_visibility="collapsed",
    )
    run_clicked = st.button("🚀 Analyze & Generate Report", type="primary")
    st.markdown("</div>", unsafe_allow_html=True)

    if run_clicked:
        if not groq_key or not e2b_key:
            st.error("Please provide both the Groq API Key and the E2B API Key in the sidebar.")
        elif not query.strip():
            st.warning("Please type a question about your data first.")
        else:
            df_info = (
                f"Shape: {df.shape}\n"
                f"Columns & dtypes:\n{df.dtypes.astype(str).to_string()}\n\n"
                f"Sample rows:\n{df.head(5).to_string()}\n\n"
                f"Summary statistics:\n{df.describe(include='all').to_string()}"
            )

            # --- Run the whole Code Agent -> Sandbox -> Reporter Agent graph ---
            with st.spinner("🧠⚙️📝 Running the LangGraph pipeline (Code Agent → Sandbox → Reporter Agent)..."):
                result = run_pipeline(
                    groq_key=groq_key,
                    e2b_key=e2b_key,
                    df=df,
                    df_info=df_info,
                    query=query,
                    language=report_lang,
                )

            code = result.get("code", "")
            charts = result.get("charts", [])
            logs = result.get("logs", "")
            error = result.get("error")
            narrative = result.get("narrative", "")

            with st.expander("🔧 Generated analysis code"):
                st.code(code, language="python")

            if error:
                st.error(f"Sandbox execution error: {error}")
            if logs:
                with st.expander("📄 Execution output / findings"):
                    st.text(logs)

            if charts:
                st.subheader("📈 Generated Charts")
                cols = st.columns(2)
                for i, chart_bytes in enumerate(charts):
                    cols[i % 2].image(chart_bytes, caption=f"Chart {i + 1}", use_container_width=True)
            else:
                st.info("No charts were produced by the generated code.")

            st.subheader("🗒️ Report Narrative")
            st.write(narrative)

            # --- Build PDF ---
            with st.spinner("📄 Assembling the PDF report..."):
                out_path = os.path.join(tempfile.gettempdir(), "analysis_report.pdf")
                build_pdf_report(
                    output_path=out_path,
                    title="Data Analysis Report",
                    query=query,
                    narrative_text=narrative,
                    charts=charts,
                    data_preview=df.head(10),
                )

            with open(out_path, "rb") as f:
                st.download_button(
                    "⬇️ Download PDF Report",
                    data=f,
                    file_name="analysis_report.pdf",
                    mime="application/pdf",
                )
else:
    st.info("👆 Upload a CSV, Excel, or JSON file above to get started.")