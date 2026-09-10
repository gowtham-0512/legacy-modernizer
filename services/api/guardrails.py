import ast
import re
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field, field_validator

# -------------------------------------------------------------------------
# 1. Deterministic Python Syntax Guardrail (Zero-Cost AST)
# -------------------------------------------------------------------------

def validate_python_syntax(filename: str, code_content: str) -> Tuple[bool, Optional[str]]:
    """
    Parses Python source code into an Abstract Syntax Tree (AST).
    Returns (True, None) if syntax is valid, or (False, error_description).
    Consumes 0 API calls and runs in < 5ms.
    """
    try:
        ast.parse(code_content, filename=filename)
        return True, None
    except SyntaxError as e:
        desc = f"SyntaxError in {filename} at line {e.lineno}, col {e.offset}: {e.msg}"
        return False, desc
    except Exception as e:
        return False, f"AST Parsing Error in {filename}: {str(e)}"


class FastAPIDecoratorSanitizer(ast.NodeTransformer):
    """
    Universal AST compiler-level guardrail for FastAPI route decorators.
    Inspects all @app.(get|post|put|delete|patch) and @router.(get|post|put|delete|patch).
    Enforces the official FastAPI signature:
    - Automatically maps status aliases ('response_status', 'status', 'http_status') to 'status_code'.
    - Automatically drops ANY unapproved hallucinated keyword arguments (e.g. 'response_list', 'response_type', etc.).
    """
    ALLOWED_KWARGS = {
        'response_model', 'status_code', 'tags', 'dependencies',
        'summary', 'description', 'response_description', 'responses',
        'deprecated', 'operation_id', 'response_class', 'include_in_schema',
        'name', 'methods', 'response_model_include', 'response_model_exclude',
        'response_model_by_alias', 'response_model_exclude_unset',
        'response_model_exclude_defaults', 'response_model_exclude_none',
        'callbacks', 'openapi_extra', 'generate_unique_id_function'
    }

    STATUS_ALIASES = {'response_status', 'status', 'http_status'}

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr in {'get', 'post', 'put', 'delete', 'patch', 'options', 'head'}:
                    new_keywords = []
                    for kw in dec.keywords:
                        if kw.arg in self.STATUS_ALIASES:
                            kw.arg = 'status_code'
                            new_keywords.append(kw)
                        elif kw.arg in self.ALLOWED_KWARGS:
                            new_keywords.append(kw)
                        # All other unknown kwargs are safely and silently stripped!
                    dec.keywords = new_keywords
        return node


def sanitize_python_files(files_dict: Dict[str, str]) -> Dict[str, str]:
    """
    Deterministically sanitizes and corrects common LLM syntax/parameter hallucinations
    using both AST transformation and regex normalizations.
    """
    sanitized = {}
    for fname, code in files_dict.items():
        if fname.endswith(".py"):
            # 1. Universal AST FastAPI decorator sanitizer
            try:
                tree = ast.parse(code)
                new_tree = FastAPIDecoratorSanitizer().visit(tree)
                ast.fix_missing_locations(new_tree)
                code = ast.unparse(new_tree)
            except Exception:
                # Fallback to targeted regexes if AST parse fails before cleanup
                code = re.sub(r"\bresponse_status\s*=", "status_code=", code)
                code = re.sub(r",\s*response_list\s*=\s*[a-zA-Z0-9_.]+", "", code)
                code = re.sub(r"\bresponse_list\s*=\s*[a-zA-Z0-9_.]+,\s*", "", code)

            # 2. Fix illegal trailing commas in single-line imports for Python 3.14+
            code = re.sub(r'^(from\s+[^\n()]+\s+import\s+[^\n()]+?),\s*$', r'\1', code, flags=re.MULTILINE)
            code = re.sub(r'^(import\s+[^\n()]+?),\s*$', r'\1', code, flags=re.MULTILINE)

            # 3. Fix common dotenv import typo
            code = re.sub(r'\bfrom\s+dotenv\s+import\s+load\b', 'from dotenv import load_dotenv', code)

            # 4. Fix unsupported rightjoin in SQLAlchemy/SQLite
            code = re.sub(r"\.rightjoin\(", ".outerjoin(", code)

            # 5. Normalize static directory mounts in main.py
            if fname.endswith("main.py") and "StaticFiles" in code:
                code = re.sub(
                    r"if\s+os\.path\.exists\(['\"]static['\"]\):\s*\n\s*app\.mount\(['\"/]+['\"],\s*StaticFiles\(directory=['\"]static['\"][^\)]*\)[^\)]*\)",
                    "for _d in ('frontend', 'static'):\n    if os.path.exists(_d):\n        app.mount('/', StaticFiles(directory=_d, html=True), name='spa')\n        break",
                    code
                )

            # 6. Normalize Pydantic V1 class Config to Pydantic V2 ConfigDict
            if "class Config:" in code:
                code = re.sub(
                    r"class\s+Config\s*:\s*\n\s*(?:orm_mode|from_attributes)\s*=\s*True",
                    "model_config = ConfigDict(from_attributes=True)",
                    code
                )
                if "ConfigDict" in code and "from pydantic import" in code:
                    if not re.search(r"from\s+pydantic\s+import\s+[^;\n]*\bConfigDict\b", code):
                        code = re.sub(
                            r"from\s+pydantic\s+import\s+",
                            "from pydantic import ConfigDict, ",
                            code,
                            count=1
                        )

            # 7. Normalize CRUD function calls in main.py to positional arguments
            if fname.endswith("main.py") and "crud." in code:
                code = re.sub(r'\bcrud\.([a-zA-Z0-9_]+)\(db\s*=\s*db,\s*[a-zA-Z0-9_]+\s*=\s*([a-zA-Z0-9_]+)\)', r'crud.\1(db, \2)', code)
                code = re.sub(r'\bcrud\.([a-zA-Z0-9_]+)\(db\s*=\s*db\)', r'crud.\1(db)', code)
        sanitized[fname] = code

    # 5. Ensure email-validator is present in requirements.txt if EmailStr is used
    uses_email_str = any("EmailStr" in v for k, v in sanitized.items() if k.endswith(".py"))
    if uses_email_str:
        req_key = next((k for k in sanitized if k.endswith("requirements.txt")), None)
        if req_key and "email-validator" not in sanitized[req_key]:
            sanitized[req_key] = sanitized[req_key].strip() + "\nemail-validator>=2.0.0\n"

    return sanitized


def validate_all_python_files(files_dict: Dict[str, str]) -> Dict[str, str]:
    """
    Validates syntax across all generated Python files.
    Returns a dictionary of failed files: {filename: error_description}.
    """
    failures = {}
    for fname, code in files_dict.items():
        if fname.endswith(".py"):
            ok, err = validate_python_syntax(fname, code)
            if not ok:
                failures[fname] = err
    return failures


# -------------------------------------------------------------------------
# 2. Pydantic Schema Contracts (Structured Guardrail)
# -------------------------------------------------------------------------

class BusinessRuleItem(BaseModel):
    id: str
    source_file: Optional[str] = "unknown"
    description: str
    rule_type: Optional[str] = "explicit"
    confidence: Optional[str] = "high"

class ProjectInventorySchema(BaseModel):
    project_metadata: Dict[str, Any] = Field(default_factory=dict)
    configurations: List[Dict[str, Any]] = Field(default_factory=list)
    database_schemas: List[Dict[str, Any]] = Field(default_factory=list)
    structural_components: List[Dict[str, Any]] = Field(default_factory=list)
    business_rule_inventory: List[BusinessRuleItem] = Field(default_factory=list)

class OperationNodeItem(BaseModel):
    operation: str
    target_file: Optional[str] = "main.py"
    preconditions: Optional[List[str]] = Field(default_factory=list)
    postconditions: Optional[List[str]] = Field(default_factory=list)
    invariants: Optional[List[str]] = Field(default_factory=list)

class BSGContractSchema(BaseModel):
    project_architecture: Dict[str, Any] = Field(default_factory=dict)
    global_invariants: List[str] = Field(default_factory=list)
    operation_nodes: List[OperationNodeItem] = Field(default_factory=list)


# -------------------------------------------------------------------------
# 3. Secret Leakage Detection Guardrail
# -------------------------------------------------------------------------

SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic_api_key": re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*=\s*['\"][0-9a-zA-Z_\-]{16,}['\"]"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "jwt_token": re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),
}

def scan_for_secret_leaks(files_dict: Dict[str, str]) -> List[Dict[str, str]]:
    """
    Scans generated files for accidentally leaked API keys, tokens, or private keys.
    Returns list of findings: [{'file': str, 'pattern': str}].
    """
    findings = []
    for fname, content in files_dict.items():
        # Skip template example files
        if fname.endswith(".example") or fname == "requirements.txt":
            continue
        for pattern_name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append({"file": fname, "pattern": pattern_name})
    return findings


# -------------------------------------------------------------------------
# 4. Database Safety Guardrail (Read-Only Source & Destructive SQL Linter)
# -------------------------------------------------------------------------

DESTRUCTIVE_SQL_PATTERNS = [
    (re.compile(r"(?i)\bDROP\s+DATABASE\b"), "DROP DATABASE statement blocked"),
    (re.compile(r"(?i)\bDROP\s+TABLE\s+(?!IF\s+EXISTS)"), "Unconditional DROP TABLE statement blocked"),
    (re.compile(r"(?i)\bTRUNCATE\s+TABLE\b"), "TRUNCATE TABLE statement blocked"),
]

def lint_sql_safety(code_or_sql: str) -> Tuple[bool, List[str]]:
    """
    Guarantees the read-only source principle: rejects scripts containing
    unsafe, destructive operations that could wipe source databases.
    """
    violations = []
    for pattern, rule_name in DESTRUCTIVE_SQL_PATTERNS:
        if pattern.search(code_or_sql):
            violations.append(rule_name)
    return len(violations) == 0, violations
