"""
graph.py
Orchestrates the whole pipeline as a LangGraph StateGraph:

    START -> code_agent -> sandbox -> reporter_agent -> END

Each node reads/writes a shared `PipelineState` dict. This replaces the
manual, sequential function calls in app.py with an explicit, inspectable
graph - the same pattern you'd use for a bigger multi-agent system.
"""

from typing import Optional, TypedDict

import pandas as pd
from langgraph.graph import StateGraph, START, END

from agents import get_client, generate_analysis_code, generate_report_narrative
from sandbox_executor import run_analysis_in_sandbox


class PipelineState(TypedDict, total=False):
    # --- inputs ---
    groq_key: str
    e2b_key: str
    df: pd.DataFrame
    df_info: str
    query: str
    language: str

    # --- produced along the way ---
    code: str
    charts: list
    logs: str
    error: Optional[str]
    narrative: str


# ----------------------------------------------------------------------------
# Nodes - each one takes the current state and returns a partial update
# ----------------------------------------------------------------------------

def code_agent_node(state: PipelineState) -> dict:
    """Node 1: Code Agent writes the pandas + matplotlib analysis script."""
    client = get_client(state["groq_key"])
    code = generate_analysis_code(client, state["df_info"], state["query"])
    return {"code": code}


def sandbox_node(state: PipelineState) -> dict:
    """Node 2: run the generated code inside an isolated E2B sandbox."""
    try:
        charts, logs, error = run_analysis_in_sandbox(
            state["e2b_key"], state["code"], state["df"]
        )
    except Exception as e:
        charts, logs, error = [], "", str(e)
    return {"charts": charts, "logs": logs, "error": error}


def reporter_agent_node(state: PipelineState) -> dict:
    """Node 3: Reporter Agent turns sandbox output into a narrative report."""
    client = get_client(state["groq_key"])
    exec_logs = state.get("logs") or "No text output was produced."
    narrative = generate_report_narrative(
        client,
        state["query"],
        exec_logs,
        len(state.get("charts", [])),
        state.get("language", "English"),
    )
    return {"narrative": narrative}


# ----------------------------------------------------------------------------
# Build + compile the graph once
# ----------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("code_agent", code_agent_node)
    graph.add_node("sandbox", sandbox_node)
    graph.add_node("reporter_agent", reporter_agent_node)

    graph.add_edge(START, "code_agent")
    graph.add_edge("code_agent", "sandbox")
    graph.add_edge("sandbox", "reporter_agent")
    graph.add_edge("reporter_agent", END)

    return graph.compile()


# Compiled once at import time, reused across Streamlit reruns.
_APP = build_graph()


def run_pipeline(groq_key: str, e2b_key: str, df: pd.DataFrame, df_info: str,
                  query: str, language: str = "English") -> PipelineState:
    """Convenience wrapper used by app.py - runs the whole graph end to end."""
    initial_state: PipelineState = {
        "groq_key": groq_key,
        "e2b_key": e2b_key,
        "df": df,
        "df_info": df_info,
        "query": query,
        "language": language,
    }
    return _APP.invoke(initial_state)