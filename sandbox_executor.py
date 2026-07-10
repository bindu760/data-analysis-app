"""
sandbox_executor.py
An adaptive executor that dynamically detects your installed E2B version 
and handles log formatting safely whether logs are objects or raw strings.
"""

import base64
import os
import e2b_code_interpreter

# Dynamic detection of the available class in your installed package
if hasattr(e2b_code_interpreter, 'CodeInterpreter'):
    ActiveSandboxClass = e2b_code_interpreter.CodeInterpreter
elif hasattr(e2b_code_interpreter, 'CodeInterpreterSandbox'):
    ActiveSandboxClass = e2b_code_interpreter.CodeInterpreterSandbox
elif hasattr(e2b_code_interpreter, 'Sandbox'):
    ActiveSandboxClass = e2b_code_interpreter.Sandbox
else:
    raise ImportError("Could not locate a recognizable Sandbox or CodeInterpreter class in e2b_code_interpreter.")

def run_analysis_in_sandbox(e2b_api_key: str, code: str, df):
    """
    Runs the provided Python code in an E2B sandbox, sending the dataframe 'df' along.
    Returns: (charts_bytes_list, stdout_logs, error_string)
    """
    charts = []
    logs = ""
    error = None

    if e2b_api_key:
        os.environ["E2B_API_KEY"] = e2b_api_key

    try:
        # Dynamically instantiate using whatever class your package has
        try:
            # Try factory method first (for older Sandbox variants)
            sandbox = ActiveSandboxClass.create()
        except AttributeError:
            # Fall back to direct instantiation (for standard/newer variants)
            sandbox = ActiveSandboxClass()
    except Exception as init_err:
        return charts, logs, f"E2B Sandbox Initialization Failed: {str(init_err)}"

    with sandbox:
        try:
            csv_data = df.to_csv(index=False)
            
            # Adapt file writing syntax based on v0.x vs v1.x structures
            if hasattr(sandbox, 'notebook'):
                sandbox.notebook.write_file("dataset.csv", csv_data)
            else:
                sandbox.files.write("dataset.csv", csv_data)
            
            setup_code = (
                "import pandas as pd\n"
                "import matplotlib\n"
                "matplotlib.use('Agg')\n"
                "import matplotlib.pyplot as plt\n"
                "import seaborn as sns\n"
                "df = pd.read_csv('dataset.csv')\n"
            )
            
            full_code_to_run = setup_code + "\n" + code

            # Adapt code execution syntax
            if hasattr(sandbox, 'notebook'):
                execution = sandbox.notebook.exec_cell(full_code_to_run)
            else:
                execution = sandbox.run_code(full_code_to_run)

            # 1. FIX: Safe harvest of terminal logs (handles both raw strings and objects with .line attribute)
            if execution.logs.stdout:
                extracted_lines = []
                for log in execution.logs.stdout:
                    if hasattr(log, 'line'):
                        extracted_lines.append(log.line)
                    else:
                        extracted_lines.append(str(log))  # Fallback for raw strings
                logs = "\n".join(extracted_lines)
            
            # 2. Extract errors safely
            if execution.error:
                error = f"{execution.error.name}: {execution.error.value}\n{execution.error.traceback}"
                return charts, logs, error

            # 3. Retrieve render buffers
            if hasattr(execution, 'results'):
                for result in execution.results:
                    if result.png:
                        chart_bytes = base64.b64decode(result.png)
                        if chart_bytes not in charts:
                            charts.append(chart_bytes)

            # Check local file fallback if no inline charts were fetched
            if not charts:
                try:
                    if hasattr(sandbox, 'notebook'):
                        chart_bytes = sandbox.notebook.read_file("chart.png", format="bytes")
                    else:
                        chart_bytes = sandbox.files.read("chart.png", format="bytes")
                    if chart_bytes and len(chart_bytes) > 0:
                        charts.append(chart_bytes)
                except Exception:
                    pass
                        
        except Exception as run_err:
            error = f"Error during execution inside sandbox: {str(run_err)}"

    return charts, logs, error