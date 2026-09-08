"""Evaluate a generated modernization result without calling an LLM.

Usage:
  py evals/run_evals.py --source-dir test-fixtures/java --generated-dir path/to/generated-project
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path(__file__).resolve().parent / "results"
SOURCE_SUFFIXES = {".java", ".sql", ".properties", ".xml", ".json", ".yaml", ".yml", ".gradle"}
REQUIRED_OUTPUTS = {"main.py", "database.py", "models.py", "schemas.py", "requirements.txt", ".env.example"}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic_api_key": re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*=\s*['\"][^'\"]{12,}['\"]"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
}


def eligible_source_files(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.rglob("*") if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES)


def compile_python_files(generated_dir: Path) -> tuple[int, list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    files = sorted(generated_dir.rglob("*.py"))
    for path in files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as error:
            failures.append({"file": str(path.relative_to(generated_dir)), "error": str(error)})
    return len(files), failures


def find_secret_leaks(generated_dir: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in generated_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".txt", ".json", ".yml", ".yaml", ".properties", ".env"}:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append({"file": str(path.relative_to(generated_dir)), "pattern": label})
    return findings


def run_generated_tests(generated_dir: Path) -> dict[str, Any]:
    test_file = generated_dir / "test_suite.py"
    if not test_file.exists():
        return {"status": "not_available", "reason": "test_suite.py was not generated"}
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", test_file.name], cwd=generated_dir,
        text=True, capture_output=True, env=environment, timeout=120, check=False,
    )
    return {"status": "passed" if result.returncode == 0 else "failed", "return_code": result.returncode, "output": (result.stdout + result.stderr)[-4000:]}


def evaluate(source_dir: Path, generated_dir: Path, run_tests: bool) -> dict[str, Any]:
    if not source_dir.is_dir() or not generated_dir.is_dir():
        raise ValueError("Both --source-dir and --generated-dir must be existing directories.")
    source_files = eligible_source_files(source_dir)
    missing_outputs = sorted(name for name in REQUIRED_OUTPUTS if not (generated_dir / name).is_file())
    python_files, syntax_failures = compile_python_files(generated_dir)
    test_result = run_generated_tests(generated_dir) if run_tests else {"status": "not_run"}
    secret_findings = find_secret_leaks(generated_dir)
    metrics = {
        "source_files_discovered": len(source_files),
        "required_artifacts_present": len(REQUIRED_OUTPUTS) - len(missing_outputs),
        "required_artifacts_expected": len(REQUIRED_OUTPUTS),
        "artifact_completeness_percent": round(100 * (len(REQUIRED_OUTPUTS) - len(missing_outputs)) / len(REQUIRED_OUTPUTS), 2),
        "python_files_checked": python_files,
        "syntax_pass_rate_percent": round(100 * (python_files - len(syntax_failures)) / python_files, 2) if python_files else 0.0,
        "secret_leaks_detected": len(secret_findings),
    }
    passed = not missing_outputs and not syntax_failures and not secret_findings
    if run_tests:
        passed = passed and test_result["status"] == "passed"
    return {"evaluated_at": datetime.now(UTC).isoformat(), "source_dir": str(source_dir), "generated_dir": str(generated_dir), "passed": passed, "metrics": metrics, "missing_required_artifacts": missing_outputs, "syntax_failures": syntax_failures, "secret_findings": secret_findings, "generated_test_result": test_result, "notes": ["A passing result proves artifact quality, not behavioral equivalence.", "Add fixture-specific acceptance tests before production use."]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a generated Legacy Modernizer project.")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--generated-dir", type=Path, required=True)
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.source_dir.resolve(), args.generated_dir.resolve(), args.run_tests)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / f"evaluation-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved report: {report_path.relative_to(PROJECT_ROOT)}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
