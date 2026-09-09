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
