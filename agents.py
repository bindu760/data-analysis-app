"""
agents.py
Two AI "agents" built on top of the Groq API:

1. Code Agent      -> reads the dataframe schema + user question, writes a
                      complete, runnable Python analysis script (pandas +
                      matplotlib) that will later be executed inside an
                      E2B sandbox.

2. Reporter Agent  -> reads the execution logs / findings produced by the
                      Code Agent's script and writes a clean, structured,
                      business-style narrative report (used later to build
                      the PDF).
"""

from groq import Groq

# A powerful and highly capable model on Groq suitable for both coding and data reporting tasks
MODEL = "llama-3.3-70b-versatile"


def get_client(api_key: str) -> Groq:
    """Creates and returns an initialized Groq client instance."""
    return Groq(api_key=api_key)


def _extract_text(response) -> str:
    """Extracts and cleans the text content from the Groq API completion response."""
    return response.choices[0].message.content.strip()


def _strip_code_fences(code: str) -> str:
    """Removes standard markdown triple-backtick fences if present in the LLM output."""
    code = code.strip()
    if code.startswith("```"):
        parts = code.split("```")
        # parts[1] usually holds "python\n<code>" or just "<code>"
        inner = parts[1]
        if inner.startswith("python"):
            inner = inner[len("python"):]
        code = inner
    return code.strip()


def generate_analysis_code(client: Groq, df_info: str, query: str) -> str:
    """Ask the Code Agent to write a full analysis script for the given data + question."""
    system = (
        "You are a senior data analyst and Python engineer. "
        "A pandas DataFrame called `df` is ALREADY loaded in memory. "
        "Given a description of that DataFrame and a user question, write a COMPLETE, "
        "RUNNABLE Python script that:\n"
        "1. Explores the columns relevant to the question.\n"
        "2. Performs whatever analysis is needed to answer it (grouping, aggregation, etc.).\n"
        "3. Creates AT LEAST ONE clear, well-labeled matplotlib or seaborn chart.\n"
        "4. Prints key numeric findings using print().\n\n"
        "CRITICAL RULES FOR CHARTS:\n"
        "- You MUST create at least one chart using matplotlib or seaborn.\n"
        "- Give the chart a title, labels, and call plt.figure() before creating it.\n"
        "- ALWAYS save your chart as an image file named 'chart.png' at the very end of your script using `plt.savefig('chart.png', bbox_inches='tight')`.\n"
        "- NEVER call plt.show() or any other save function. Only save to 'chart.png'.\n"
        "- Respond with RAW PYTHON CODE ONLY - no markdown fences, no commentary."
    )
    user_msg = f"DataFrame info:\n{df_info}\n\nUser question: {query}\n\nWrite the full python analysis script now."

    # Using Groq's Chat Completions API with a low temperature for predictable code output
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg}
        ],
    )
    return _strip_code_fences(_extract_text(resp))


def generate_report_narrative(
    client: Groq,
    query: str,
    exec_logs: str,
    chart_count: int,
    language: str = "English",
) -> str:
    """Ask the Reporter Agent to turn raw execution output into a polished narrative."""
    lang_instruction = "Nepali (नेपाली, Devanagari script)" if language == "Nepali" else "English"
    system = (
        f"You are a professional data analysis reporter. Write the ENTIRE report in {lang_instruction}. "
        "Produce a structured report using these exact section headers, in plain text (no markdown "
        "symbols like # or *):\n"
        "TITLE\nEXECUTIVE SUMMARY\nKEY FINDINGS\nCHART INSIGHTS\nRECOMMENDATIONS\nCONCLUSION\n\n"
        f"There are {chart_count} chart(s) produced by the analysis - refer to them as Chart 1, "
        "Chart 2, etc. in the CHART INSIGHTS section. KEY FINDINGS should be short, one-line points "
        "(one per line, no bullet characters needed). Keep the whole report concise, grounded ONLY "
        "in the execution output provided below, and business-appropriate in tone."
    )
    user_msg = f"User question: {query}\n\nCode execution output/logs:\n{exec_logs}\n\nWrite the report now."

    # Using Groq's Chat Completions API to generate the final formatted narrative report
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg}
        ],
    )
    return _extract_text(resp)