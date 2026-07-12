"""
sandbox_executor.py
Runs the Code Agent's generated script safely inside an E2B cloud sandbox
and pulls back:
  - any matplotlib charts produced (as raw PNG bytes)
  - stdout / stderr logs (used later as input for the Reporter Agent)
  - an error message, if the script raised one
"""

import base64
from e2b_code_interpreter import Sandbox


def run_analysis_in_sandbox(e2b_api_key: str, code: str, df):
    """
    df  : the pandas DataFrame currently loaded in Streamlit.
    code: the python analysis script written by the Code Agent
          (it assumes a variable `df` already exists).

    Returns: (charts: list[bytes], logs: str, error: str | None)
    """
    charts = []
    logs_parts = []
    error = None

    sbx = Sandbox.create(api_key=e2b_api_key)
    try:
        # Ship the current dataframe into the sandbox as a CSV file
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        sbx.files.write("/home/user/data.csv", csv_bytes)

        setup_code = (
            "import pandas as pd\n"
            "df = pd.read_csv('/home/user/data.csv')\n"
        )
        # Safety net: even if the generated code forgets to call plt.show()
        # for one or more figures, force-show any figures still open so
        # E2B captures them as chart results.
        capture_code = (
            "\n\ntry:\n"
            "    import matplotlib.pyplot as _plt\n"
            "    for _fignum in _plt.get_fignums():\n"
            "        _plt.figure(_fignum)\n"
            "        _plt.show()\n"
            "except Exception as _e:\n"
            "    print('chart auto-capture skipped:', _e)\n"
        )
        full_code = setup_code + "\n" + code + capture_code

        execution = sbx.run_code(full_code)

        if execution.logs:
            if execution.logs.stdout:
                logs_parts.append("".join(execution.logs.stdout))
            if execution.logs.stderr:
                logs_parts.append("[STDERR]\n" + "".join(execution.logs.stderr))

        if execution.error:
            error = f"{execution.error.name}: {execution.error.value}"

        for result in execution.results:
            if getattr(result, "png", None):
                charts.append(base64.b64decode(result.png))
    finally:
        sbx.kill()

    return charts, "\n".join(logs_parts), error