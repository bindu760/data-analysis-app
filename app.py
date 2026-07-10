import io
import os
import json
import tempfile

import pandas as pd
import streamlit as st
from dotenv import load_dotenv  # Loads keys from a .env file automatically

from agents import get_client, generate_analysis_code, generate_report_narrative
from sandbox_executor import run_analysis_in_sandbox
from pdf_report import build_pdf_report

# Load environment variables from a .env file if it exists
load_dotenv()

# Fetch API Keys directly from the backend environment
groq_key = os.environ.get("GROQ_API_KEY", "")
e2b_key = os.environ.get("E2B_API_KEY", "")

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
    width: 100%;
}
div.stDownloadButton > button {
    background: linear-gradient(120deg, #1f6f43, #2ea862);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    width: 100%;
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
# Sidebar - configuration (Simplified: API Key fields removed)
# ----------------------------------------------------------------------------
st.sidebar.header("⚙️ Settings")
report_lang = st.sidebar.selectbox("Report language", ["English", "Nepali"])

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
            for key in ("data", "records", "rows"):
                if key in raw and isinstance(raw[key], list):
                    return pd.json_normalize(raw[key])
            return pd.json_normalize(raw)
        raise ValueError("Unsupported JSON structure.")
    raise ValueError("Unsupported file type.")

# Reset analysis state if a completely new file is uploaded
if uploaded_file is not None:
    if st.session_state.get("current_filename") != uploaded_file.name:
        st.session_state["df"] = None
        st.session_state["filename"] = uploaded_file.name
        st.session_state["current_filename"] = uploaded_file.name
        for key in ["analysis_code", "sandbox_logs", "sandbox_charts", "sandbox_error", "narrative", "pdf_path"]:
            if key in st.session_state:
                del st.session_state[key]
                
    if st.session_state.get("df") is None:
        try:
            st.session_state["df"] = load_dataframe(uploaded_file)
        except Exception as e:
            st.error(f"Could not read this file: {e}")

# ----------------------------------------------------------------------------
# Main workflow
# ----------------------------------------------------------------------------
if st.session_state.get("df") is not None:
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
            st.error("Missing API Keys! Please ensure GROQ_API_KEY and E2B_API_KEY are properly configured in your environment or .env file.")
        elif not query.strip():
            st.warning("Please type a question about your data first.")
        else:
            for key in ["analysis_code", "sandbox_logs", "sandbox_charts", "sandbox_error", "narrative", "pdf_path"]:
                st.session_state.pop(key, None)

            client = get_client(groq_key)

            # --- Code Agent ---
            with st.spinner("🧠 Code Agent is writing the analysis script..."):
                df_info = (
                    f"Shape: {df.shape}\n"
                    f"Columns & dtypes:\n{df.dtypes.astype(str).to_string()}\n\n"
                    f"Sample rows:\n{df.head(5).to_string()}\n\n"
                    f"Summary statistics:\n{df.describe(include='all').to_string()}"
                )
                code = generate_analysis_code(client, df_info, query)
                st.session_state["analysis_code"] = code

            # --- E2B sandbox execution ---
            with st.spinner("⚙️ Running the code inside an isolated E2B sandbox..."):
                try:
                    charts, logs, error = run_analysis_in_sandbox(e2b_key, code, df)
                except Exception as e:
                    charts, logs, error = [], "", str(e)
                
                st.session_state["sandbox_logs"] = logs
                st.session_state["sandbox_charts"] = charts
                st.session_state["sandbox_error"] = error

            # --- Reporter Agent ---
            with st.spinner("📝 Reporter Agent is writing the narrative..."):
                narrative = generate_report_narrative(
                    client, query, logs or "No text output was produced.", len(charts), report_lang,
                )
                st.session_state["narrative"] = narrative

            # --- Build PDF ---
            with st.spinner("📄 Assembling the PDF report..."):
                out_path = os.path.join(tempfile.gettempdir(), f"analysis_report_{int(pd.Timestamp.now().timestamp())}.pdf")
                build_pdf_report(
                    output_path=out_path,
                    title="Data Analysis Report",
                    query=query,
                    narrative_text=narrative,
                    charts=charts,
                    data_preview=df.head(10),
                )
                st.session_state["pdf_path"] = out_path
            
            st.rerun()

    # --- RENDERING PHASE ---
    if "analysis_code" in st.session_state:
        st.markdown("---")
        st.header("📊 Analysis Execution & Results")
        
        with st.expander("🔧 View Generated Analysis Code"):
            st.code(st.session_state["analysis_code"], language="python")

        # Display sandbox execution error if any exists
        if st.session_state.get("sandbox_error"):
            st.error("⚠️(Sandbox Execution Error):")
            st.code(st.session_state["sandbox_error"], language="python")

        if st.session_state.get("sandbox_logs"):
            with st.expander("📄 Raw Execution Findings / Terminal Output"):
                st.text(st.session_state["sandbox_logs"])

        charts = st.session_state.get("sandbox_charts", [])
        if charts:
            st.subheader("📈 Generated Data Visualizations")
            cols = st.columns(min(len(charts), 2))
            for i, chart_bytes in enumerate(charts):
                cols[i % 2].image(chart_bytes, caption=f"Chart {i + 1}", use_container_width=True)
        else:
            st.info("No charts were produced by the generated code.")

        if "narrative" in st.session_state:
            st.subheader("🗒️ Executive Summary & Insights")
            st.markdown(st.session_state["narrative"])

        if "pdf_path" in st.session_state and os.path.exists(st.session_state["pdf_path"]):
            st.markdown("---")
            with open(st.session_state["pdf_path"], "rb") as f:
                st.download_button(
                    label="⬇️ Download Complete PDF Report",
                    data=f,
                    file_name=f"Data_Analysis_Report_{st.session_state.get('filename', 'export')}.pdf",
                    mime="application/pdf",
                )
else:
    st.info("👆 Upload a CSV, Excel, or JSON file above to get started.")