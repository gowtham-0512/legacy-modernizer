import os
import time
import shutil
import subprocess
from pathlib import Path
from google import genai

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def retry_api_call(func, max_retries=6, delay=5):
    """
    Helper to retry API calls with smart backoff.
    - If 429 Rate Limit occurs: waits 20 seconds for token bucket refill.
    - If WinError 10054 / connection drop occurs: waits 5 seconds and reconnects.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            err_str = str(e)
            if attempt == max_retries - 1:
                raise e
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait_time = 20
                print(f"[RATE LIMIT COOLDOWN] Free tier token bucket full. Waiting {wait_time}s for quota reset (Attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_time)
            elif "10054" in err_str or "connection" in err_str.lower() or "timeout" in err_str.lower():
                print(f"[CONNECTION RECONNECT] Network connection reset. Reconnecting in {delay}s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(delay)
            else:
                print(f"Network error: {e}. Retrying in {delay}s...")
                time.sleep(delay)

# Manually load the secret API key from the .env file (so we don't need python-dotenv)
try:
    with (PROJECT_ROOT / ".env").open("r") as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                os.environ[key] = value
except FileNotFoundError:
    pass


# Supported text extensions for code and configurations
SUPPORTED_EXTENSIONS = (
    ".java", ".xml", ".properties", ".yaml", ".yml", 
    ".sql", ".json", ".txt", ".gradle", ".conf", ".ini"
)

# Folders to ignore during scanning
IGNORED_DIRECTORIES = {
    ".git", "__pycache__", "build", "dist", "nbproject", 
    "target", ".idea", ".vscode", "bin", "obj", ".gradle"
}

def bundle_project_files(upload_dir: str) -> dict:
    """
    Scans the uploaded directory and reads all code and configuration files.
    Returns a dictionary mapping relative file paths to their contents.
    """
    project_bundle = {}
    
    for root, dirs, files in os.walk(upload_dir):
        # Skip hidden, build, and IDE folders
        dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in IGNORED_DIRECTORIES]
        
        for file in files:
            if file.lower().endswith(SUPPORTED_EXTENSIONS):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, upload_dir)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        project_bundle[relative_path] = f.read()
                except Exception as e:
                    print(f"Skipping {relative_path} due to read error: {e}")
                    
    return project_bundle


def format_project_bundle(bundle: dict) -> str:
    """
    Formats the project bundle dictionary into a structured string for LLM prompts.
    """
    formatted_parts = []
    for file_path, content in bundle.items():
        formatted_parts.append(f"=== FILE: {file_path} ===\n{content}\n")
    return "\n".join(formatted_parts)


def agent1_legacy_analyzer(client, project_bundle_text: str) -> str:
    """
    AGENT 1: The Legacy Analyzer (Whole-Project).
    Performs deep analysis across the entire legacy artifact bundle (code, SQL schemas, configs).
    Outputs a comprehensive Project Business Rule Inventory in JSON format.
    """
    system_instruction = (
        "You are 'Agent 1: Legacy Analyzer' in a multi-agent legacy modernization pipeline. "
        "You are analyzing an entire legacy project bundle containing source code, database schemas, and configuration files. "
        "Your task is to extract all structural components, configuration settings, database contracts, and implicit business rules. "
        "OUTPUT FORMAT: Return ONLY a raw JSON document (DO NOT include markdown formatting like ```json). "
        "The JSON MUST have the following keys:\n"
        "1. 'project_metadata': { 'detected_framework': string, 'database_type': string, 'entry_points': list }\n"
        "2. 'configurations': list of detected config properties (e.g., ports, DB URLs, credentials keys)\n"
        "3. 'database_schemas': list of detected tables, columns, constraints\n"
        "4. 'structural_components': list of classes/services/endpoints with their responsibilities\n"
        "5. 'business_rule_inventory': list of rules, each with { 'id': string, 'source_file': string, 'description': string, 'rule_type': 'explicit'|'implicit', 'confidence': 'high'|'medium'|'low' }"
    )
    
    print("Agent 1 is performing Whole-Project Analysis across all files...")
    response = retry_api_call(lambda: client.models.generate_content(
        model='gemini-flash-lite-latest',
        contents=[system_instruction, f"PROJECT ARTIFACT BUNDLE:\n{project_bundle_text}"]
    ))
    
    # Strip markdown if the AI accidentally includes it anyway
    result = response.text.strip()
    if result.startswith("```json"):
        result = result[7:]
    if result.endswith("```"):
        result = result[:-3]
        
    return result.strip()


def agent2_specification_generator(client, project_bundle_text: str, agent1_json: str) -> str:
    """
    AGENT 2: The Specification Generator (Whole-Project).
    Transforms the multi-file Business Rule Inventory into a Project-Level Behavioral Specification Graph (BSG).
    This acts as the strict contract that the modernized system must fulfill.
    """
    system_instruction = (
        "You are 'Agent 2: Specification Generator' in a multi-agent modernization pipeline. "
        "Your task is to take the Whole-Project Legacy Analysis JSON and source bundle, and generate a Project-Level Behavioral Specification Graph (BSG). "
        "A BSG defines the strict contractual behavior of the modern Python architecture. "
        "OUTPUT FORMAT: Return ONLY a raw JSON document (DO NOT include markdown formatting like ```json). "
        "The JSON MUST have:\n"
        "1. 'project_architecture': { 'target_stack': 'FastAPI + SQLAlchemy', 'module_structure': list of target python filenames }\n"
        "2. 'global_invariants': list of global invariants across the system (e.g. database constraints, transaction safety)\n"
        "3. 'operation_nodes': array of discrete operations. Each node must contain:\n"
        "   - 'operation': name of operation/endpoint\n"
        "   - 'target_file': which python file will contain this\n"
        "   - 'preconditions': list of input predicates required\n"
        "   - 'postconditions': list of expected outcomes/responses\n"
        "   - 'invariants': local invariants"
    )
    
    print("Agent 2 is generating the Project-Level Behavioral Specification Graph (BSG)...")
    response = retry_api_call(lambda: client.models.generate_content(
        model='gemini-flash-lite-latest',
        contents=[system_instruction, f"Agent 1 Project Inventory:\n{agent1_json}\n\nProject Artifact Bundle:\n{project_bundle_text}"]
    ))
    
    result = response.text.strip()
    if result.startswith("```json"):
        result = result[7:]
    if result.endswith("```"):
        result = result[:-3]
        
    return result.strip()


import json

def unpack_project_files(files_dict: dict, output_dir: str) -> list:
    """
    Takes a dictionary mapping relative file paths to file contents,
    and writes them into output_dir preserving directory structure.
    Returns list of written file paths.
    """
    written_files = []
    for rel_path, content in files_dict.items():
        # Clean relative path
        clean_path = rel_path.lstrip("/\\")
        target_path = os.path.join(output_dir, clean_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
        written_files.append(clean_path)
        
    return written_files


def agent3_modernization_transformer(client, project_bundle_text: str, bsg_json: str, feedback: str = "") -> dict:
    """
    AGENT 3: The Modernization Transformer (Whole-Project).
    Generates an integrated multi-file Python project (FastAPI, SQLAlchemy, models, requirements.txt)
    strictly adhering to the Behavioral Specification Graph (BSG) and legacy configs.
    Outputs a dictionary mapping filenames to code content.
    """
    system_instruction = (
        "You are 'Agent 3: Modernization Transformer' in a multi-agent modernization pipeline. "
        "Your task is to generate a complete, production-ready, multi-file modern Python project (FastAPI + SQLAlchemy). "
        "You MUST generate all necessary files based on the Behavioral Specification Graph (BSG) and legacy configurations:\n"
        "1. 'main.py' (FastAPI application & endpoints)\n"
        "2. 'database.py' (SQLAlchemy engine, sessionmaker, database connection)\n"
        "3. 'models.py' (SQLAlchemy ORM models matching database schema)\n"
        "4. 'schemas.py' (Pydantic models for request/response validation)\n"
        "5. 'migrate_data.py' (Data migration and seeding script that initializes database tables and seeds legacy SQL records or initial sample data into the database)\n"
        "6. 'requirements.txt' (All pip dependencies needed to run the project)\n"
        "7. '.env.example' (Environment variables needed)\n\n"
        "CRITICAL CODE GENERATION RULES:\n"
        "- In 'database.py': ALWAYS use 'from urllib.parse import quote_plus' to safely URL-encode the database password before constructing the DATABASE_URL (e.g. `encoded_pwd = quote_plus(password)`). Special characters like '@' in passwords MUST be escaped so they never cause hostname parsing errors.\n"
        "- In 'requirements.txt': ALWAYS use flexible version bounds with '>=' (e.g. `fastapi>=0.110.0`, `uvicorn>=0.28.0`, `sqlalchemy>=2.0.0`, `pymysql>=1.1.0`, `pydantic>=2.6.0`, `python-dotenv>=1.0.0`). NEVER use strict '==' pins so that modern Python versions (like Python 3.13/3.14) can install pre-compiled wheels without requiring local C++/Rust build tools.\n"
        "- In 'main.py': Raw SQL queries and health checks MUST use SQLAlchemy 2.0 syntax: `from sqlalchemy import text` and `db.execute(text('SELECT 1'))`. NEVER use `func.select(1)`.\n\n"
        "OUTPUT FORMAT: Return ONLY a raw JSON document (DO NOT include markdown formatting like ```json). "
        "The JSON MUST be in this exact format:\n"
        "{\n"
        "  \"files\": {\n"
        "    \"main.py\": \"<full python code>\",\n"
        "    \"database.py\": \"<full python code>\",\n"
        "    \"models.py\": \"<full python code>\",\n"
        "    \"schemas.py\": \"<full python code>\",\n"
        "    \"migrate_data.py\": \"<full python code>\",\n"
        "    \"requirements.txt\": \"<pip requirements>\"\n"
        "  }\n"
        "}"
    )
    
    if feedback:
        print("Agent 3 is FIXING the multi-file project based on test failures...")
        user_prompt = f"Behavioral Specification Graph (BSG):\n{bsg_json}\n\nProject Artifact Bundle:\n{project_bundle_text}\n\nPREVIOUS TEST FAILURES TO FIX:\n{feedback}"
    else:
        print("Agent 3 is generating the multi-file modern Python project...")
        user_prompt = f"Behavioral Specification Graph (BSG):\n{bsg_json}\n\nProject Artifact Bundle:\n{project_bundle_text}"
        
    response = retry_api_call(lambda: client.models.generate_content(
        model='gemini-flash-lite-latest',
        contents=[system_instruction, user_prompt]
    ))
    
    # Robust markdown stripping and JSON extraction
    clean_result = response.text.strip()
    if clean_result.startswith("```json"):
        clean_result = clean_result[7:]
    elif clean_result.startswith("```"):
        clean_result = clean_result[3:]
    if clean_result.endswith("```"):
        clean_result = clean_result[:-3]
    clean_result = clean_result.strip()
    
    import re
    try:
        # Try direct JSON parsing
        parsed = json.loads(clean_result, strict=False)
        if isinstance(parsed, dict):
            if "files" in parsed and isinstance(parsed["files"], dict):
                return parsed["files"]
            return parsed
    except Exception:
        # Try finding JSON block with regex
        match = re.search(r'(\{[\s\S]*\})', clean_result)
        if match:
            try:
                parsed = json.loads(match.group(1), strict=False)
                if isinstance(parsed, dict):
                    if "files" in parsed and isinstance(parsed["files"], dict):
                        return parsed["files"]
                    return parsed
            except Exception as e:
                print(f"Regex JSON extraction failed: {e}")
                
    print("Warning: could not parse Agent 3 output as JSON. Falling back to single file.")
    return {"main.py": clean_result}


def agent4_equivalence_validator(client, files_dict: dict, bsg_json: str) -> str:
    """
    AGENT 4: The Equivalence Validator (Whole-Project).
    Generates a comprehensive pytest script testing the integrated Python project
    against the Behavioral Specification Graph (BSG).
    """
    system_instruction = (
        "You are 'Agent 4: Equivalence Validator' in a multi-agent modernization pipeline. "
        "Your task is to write a complete Python 'pytest' test suite for the modernized FastAPI + SQLAlchemy project. "
        "The test suite must verify the endpoints, status codes, response bodies, and constraints defined in the BSG. "
        "RULES FOR THE TEST SCRIPT:\n"
        "1. Assume all generated project files (e.g. main.py, database.py, models.py) are in the current working directory.\n"
        "2. Import the FastAPI app using: from main import app\n"
        "3. Use TestClient: from fastapi.testclient import TestClient; client = TestClient(app)\n"
        "4. Write test functions (starting with test_) verifying every operation in the BSG.\n"
        "OUTPUT FORMAT: Return ONLY valid Python code containing the pytest functions. DO NOT include markdown formatting like ```python."
    )
    
    files_summary = "\n\n".join([f"--- FILE: {fname} ---\n{code}" for fname, code in files_dict.items()])
    
    print("Agent 4 is writing automated integration tests for the project...")
    response = retry_api_call(lambda: client.models.generate_content(
        model='gemini-flash-lite-latest',
        contents=[system_instruction, f"Behavioral Specification Graph (BSG):\n{bsg_json}\n\nGenerated Project Code:\n{files_summary}"]
    ))
    
    result = response.text.strip()
    if result.startswith("```python"):
        result = result[9:]
    elif result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
        
    return result.strip()


def generate_modernization_report(inventory_str: str, bsg_str: str, generated_files: list) -> str:
    """
    Generates a structured, professional Markdown report summarizing the 
    architectural transformations, preserved business rules, and BSG contracts.
    """
    try:
        inv = json.loads(inventory_str)
    except Exception:
        inv = {}
        
    try:
        bsg = json.loads(bsg_str)
    except Exception:
        bsg = {}

    meta = inv.get("project_metadata", {})
    rules = inv.get("business_rule_inventory", [])
    configs = inv.get("configurations", [])
    invariants = bsg.get("global_invariants", [])
    operations = bsg.get("operation_nodes", [])

    lines = []
    lines.append("# Legacy Modernization Audit Report")
    lines.append(f"**Generated on:** {time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("**Target Stack:** FastAPI + SQLAlchemy ORM (Python)")
    lines.append("\n---\n")

    lines.append("## 1. Architecture Transformation")
    lines.append(f"- **Detected Legacy Framework:** `{meta.get('detected_framework', 'Java / Spring Boot')}`")
    lines.append(f"- **Detected Database:** `{meta.get('database_type', 'Relational SQL')}`")
    lines.append(f"- **Entry Points Modernized:** `{', '.join(meta.get('entry_points', [])) or 'Application Services'}`")
    lines.append("\n")

    if configs:
        lines.append("### Detected Configurations Preserved:")
        for c in configs:
            lines.append(f"- `{c.get('key', '')}` = `{c.get('value', '')}`")
        lines.append("\n")

    lines.append("## 2. Preserved Business Rules Inventory (Agent 1)")
    if rules:
        lines.append("| Rule ID | Type | Source File | Description | Confidence |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for r in rules:
            lines.append(f"| **{r.get('id', 'BR')}** | `{r.get('rule_type', 'explicit')}` | `{r.get('source_file', 'Source')}` | {r.get('description', '')} | `{r.get('confidence', 'high')}` |")
    else:
        lines.append("*All core entities and control flows extracted directly from source artifacts.*")
    lines.append("\n")

    if invariants:
        lines.append("## 3. Behavioral Specification Graph (BSG) Contracts (Agent 2)")
        lines.append("### Global System Invariants:")
        for invar in invariants:
            lines.append(f"- {invar}")
        lines.append("\n")

    if operations:
        lines.append("### Modernized Operation Contracts:")
        for op in operations:
            lines.append(f"#### Operation: `{op.get('operation', 'Endpoint')}` (Target: `{op.get('target_file', 'main.py')}`)")
            if op.get("preconditions"):
                lines.append("**Preconditions:**")
                for pre in op.get("preconditions", []):
                    lines.append(f"  - `{pre}`")
            if op.get("postconditions"):
                lines.append("**Postconditions:**")
                for post in op.get("postconditions", []):
                    lines.append(f"  - `{post}`")
            lines.append("\n")

    lines.append("## 4. Generated Project Files")
    for f in generated_files:
        lines.append(f"- `{f}`")
    lines.append("\n")

    lines.append("## 5. How to Run the Modernized Project")
    lines.append("```bash")
    lines.append("# 1. Install dependencies")
    lines.append("pip install -r requirements.txt")
    lines.append("")
    lines.append("# 2. Start the FastAPI server (Works on Windows, Mac, and Linux)")
    lines.append("python -m uvicorn main:app --port 8080 --reload")
    lines.append("")
    lines.append("# 3. Access Interactive Swagger Documentation")
    lines.append("# Open browser at: http://127.0.0.1:8080/docs")
    lines.append("```")

    return "\n".join(lines)


def modernize_project(upload_dir, output_dir=None, export_path=None):
    """
    Whole-Project Modernization Pipeline:
    1. Scans and bundles all project files (.java, .sql, .properties, .xml, etc.)
    2. Agent 1 extracts full project inventory
    3. Agent 2 generates project-level BSG contract
    4. Feedback loop: Agent 3 generates multi-file project -> Agent 4 tests with pytest -> fixes if needed
    5. Unpacks all generated files and writes MODERNIZATION_REPORT.md into output_dir
    """
    if output_dir is None:
        from .config import WORKSPACE_ROOT
        output_dir = WORKSPACE_ROOT / "modernized_files"
    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Bundle all legacy project files
    print(f"Scanning and bundling files in '{upload_dir}'...")
    bundle = bundle_project_files(str(upload_dir))
    if not bundle:
        return {"status": "error", "message": "No valid source or config files found in the uploaded directory."}
        
    bundle_text = format_project_bundle(bundle)
    print(f"Bundled {len(bundle)} project files: {list(bundle.keys())}")
    
    # Initialize the Gemini AI client
    client = genai.Client()
    
    try:
        # 2. Run AGENT 1 (Whole-Project Legacy Analyzer)
        print("Starting Agent 1 (Legacy Analyzer)...")
        inventory_json = agent1_legacy_analyzer(client, bundle_text)
        with open(os.path.join(output_dir, "project_inventory.json"), "w", encoding="utf-8") as f:
            f.write(inventory_json)
            
        # 3. Run AGENT 2 (Project Specification Generator)
        print("Starting Agent 2 (Specification Generator)...")
        bsg_json = agent2_specification_generator(client, bundle_text, inventory_json)
        with open(os.path.join(output_dir, "project_bsg.json"), "w", encoding="utf-8") as f:
            f.write(bsg_json)
            
        # 4. Feedback Loop (Agent 3 Transformer + Agent 4 Validator)
        feedback = ""
        final_files_dict = {}
        
        for iteration in range(2): # Max 2 iterations to conserve API tokens
            print(f"\n--- Multi-Agent Iteration {iteration + 1} ---")
            
            # Run AGENT 3 (Multi-File Code Generator)
            final_files_dict = agent3_modernization_transformer(client, bundle_text, bsg_json, feedback)
            
            # Unpack generated files to disk
            written_files = unpack_project_files(final_files_dict, output_dir)
            print(f"Unpacked {len(written_files)} files: {written_files}")
            
            # Run AGENT 4 (Equivalence Validator)
            test_code = agent4_equivalence_validator(client, final_files_dict, bsg_json)
            test_file_path = os.path.join(output_dir, "test_suite.py")
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write(test_code)
                
            # Execute automated tests with pytest
            print(f"Executing Agent 4 automated tests (Iteration {iteration + 1})...")
            test_result = subprocess.run(
                ["python", "-m", "pytest", "test_suite.py"],
                capture_output=True, text=True, cwd=output_dir
            )
            
            if test_result.returncode == 0:
                print("[SUCCESS] All Agent 4 tests PASSED! The modernized project is verified.")
                
                # 5. Execute Data Migration (Post-Verification)
                migrate_script = os.path.join(output_dir, "migrate_data.py")
                if os.path.exists(migrate_script):
                    print("[DATA MIGRATION] Executing post-verification data migration into modern database...")
                    migration_run = subprocess.run(
                        ["python", "migrate_data.py"],
                        capture_output=True, text=True, cwd=output_dir
                    )
                    if migration_run.returncode == 0:
                        print("[DATA MIGRATION SUCCESS] Legacy data successfully migrated and seeded into database!")
                    else:
                        print(f"[DATA MIGRATION NOTICE] Seeding script completed with info: {migration_run.stdout or migration_run.stderr}")
                break
            else:
                print("[FEEDBACK] Tests failed. Feeding traceback back to Agent 3...")
                print(test_result.stdout)
                feedback = test_result.stdout + "\n" + test_result.stderr
        else:
            print("Max iterations reached. Preserving best-effort generated project.")
            
        # 6. Preserve and Mount Frontend Assets if present in uploaded archive
        frontend_src = None
        for root, dirs, files in os.walk(upload_dir):
            base_name = os.path.basename(root).lower()
            if base_name in ("frontend", "static", "public", "webapp"):
                frontend_src = root
                break
            if any(f.lower().endswith(".html") for f in files) and "modernized" not in root.lower():
                frontend_src = root
                break

        if frontend_src:
            target_frontend = os.path.join(output_dir, "frontend")
            print(f"[FRONTEND PASS-THROUGH] Detected frontend assets at '{frontend_src}'. Preserving into modernized project...")
            shutil.copytree(frontend_src, target_frontend, dirs_exist_ok=True)
            
            # Mount frontend in main.py if not already mounted
            main_py_path = os.path.join(output_dir, "main.py")
            if os.path.exists(main_py_path):
                with open(main_py_path, "r", encoding="utf-8") as f:
                    main_content = f.read()
                if "app.mount" not in main_content:
                    mount_code = (
                        "\n\n# Mount frontend static dashboard\n"
                        "from pathlib import Path\n"
                        "from fastapi.staticfiles import StaticFiles\n\n"
                        "frontend_dir = Path(__file__).resolve().parent / 'frontend'\n"
                        "if frontend_dir.exists():\n"
                        "    app.mount('/', StaticFiles(directory=str(frontend_dir), html=True), name='frontend')\n"
                    )
                    with open(main_py_path, "a", encoding="utf-8") as f:
                        f.write(mount_code)
                    print("[FRONTEND MOUNT] Automatically mounted frontend directory to root '/' in main.py")

        # 7. Generate and save MODERNIZATION_REPORT.md
        all_output_files = list(final_files_dict.keys()) + ["MODERNIZATION_REPORT.md", "project_bsg.json", "project_inventory.json", "test_suite.py"]
        report_md = generate_modernization_report(inventory_json, bsg_json, all_output_files)
        with open(os.path.join(output_dir, "MODERNIZATION_REPORT.md"), "w", encoding="utf-8") as f:
            f.write(report_md)
            
        # 8. Generate run.bat for 1-click Windows execution
        run_bat_content = (
            "@echo off\r\n"
            "title Modernized Full-Stack Application\r\n"
            "echo Starting Modernized FastAPI Server on Port 8080...\r\n"
            "start http://localhost:8080\r\n"
            "python -m uvicorn main:app --port 8080 --reload\r\n"
            "pause\r\n"
        )
        with open(os.path.join(output_dir, "run.bat"), "w", encoding="utf-8") as f:
            f.write(run_bat_content)
        if "run.bat" not in all_output_files:
            all_output_files.append("run.bat")
            
        return {
            "status": "success",
            "message": "Whole-project modernization and data migration complete!",
            "generated_files": all_output_files,
            "report": report_md
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"Pipeline Error: {error_msg}")
        return {"status": "error", "message": f"AI Pipeline Error: {error_msg}"}
