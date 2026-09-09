"""Evaluate a generated modernization result without calling an LLM.

Usage:
  # Evaluate Python target:
  python evals/run_evals.py --source-dir test-fixtures/java --generated-dir path/to/generated-project --target-profile fastapi-sqlalchemy

  # Evaluate Spring Boot target:
  python evals/run_evals.py --source-dir test-fixtures/java --generated-dir path/to/generated-project --target-profile spring-boot-jpa
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
SOURCE_SUFFIXES = {".java", ".sql", ".properties", ".xml", ".json", ".yaml", ".yml", ".gradle", ".jsp"}

PROFILE_REQUIRED_OUTPUTS = {
    "fastapi-sqlalchemy": {"main.py", "database.py", "models.py", "schemas.py", "requirements.txt", ".env.example"},
    "spring-boot-jpa": {"pom.xml", "application.properties"},
}

SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "generic_api_key": re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*=\s*['\"][0-9a-zA-Z_\-]{16,}['\"]"),
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


def check_java_syntax_and_structure(generated_dir: Path) -> tuple[int, list[dict[str, str]]]:
    """Lightweight structural syntax validator for generated Java files without requiring local JDK."""
    failures: list[dict[str, str]] = []
    files = sorted(generated_dir.rglob("*.java"))
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            # Check balanced curly braces
            open_braces = text.count("{")
            close_braces = text.count("}")
            if open_braces != close_braces:
                failures.append({
                    "file": str(path.relative_to(generated_dir)),
                    "error": f"Unbalanced curly braces: {open_braces} open vs {close_braces} close"
                })
            # Check for class or interface declaration
            if not re.search(r"\b(class|interface|record|enum)\s+[A-Za-z0-9_]+", text):
                failures.append({
                    "file": str(path.relative_to(generated_dir)),
                    "error": "No valid Java class, interface, record, or enum declaration found"
                })
        except Exception as err:
            failures.append({"file": str(path.relative_to(generated_dir)), "error": str(err)})
    return len(files), failures


def find_secret_leaks(generated_dir: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in generated_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".txt", ".json", ".yml", ".yaml", ".properties", ".env", ".java"}:
            continue
        if path.name.endswith(".example"):
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append({"file": str(path.relative_to(generated_dir)), "pattern": label})
    return findings


def check_fixture_acceptance(source_dir: Path, generated_dir: Path, target_profile: str) -> dict[str, Any]:
    """
    Fixture-specific acceptance checks: verifies whether the modernized application
    retains the core business domain of the legacy source (e.g., users, departments, endpoints).
    """
    domain_checks = {
        "user_entity_preserved": False,
        "department_field_preserved": False,
        "users_api_endpoint_present": False,
    }

    all_generated_text = ""
    for p in generated_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".py", ".java", ".sql", ".properties", ".json"}:
            all_generated_text += "\n" + p.read_text(encoding="utf-8", errors="ignore")

    # Check for user entity
    if re.search(r"(?i)\bclass\s+User\b|table.*users|users_table", all_generated_text):
        domain_checks["user_entity_preserved"] = True

    # Check for department field
    if re.search(r"(?i)department", all_generated_text):
        domain_checks["department_field_preserved"] = True

    # Check for users endpoint
    if re.search(r"(?i)/users|@RequestMapping.*users|@GetMapping.*users|@app\.get.*users", all_generated_text):
        domain_checks["users_api_endpoint_present"] = True

    checks_passed = sum(1 for v in domain_checks.values() if v)
    total_checks = len(domain_checks)

    return {
        "domain_checks": domain_checks,
        "acceptance_score_percent": round(100.0 * checks_passed / total_checks, 2),
        "passed": checks_passed == total_checks
    }


def run_generated_tests(generated_dir: Path, target_profile: str) -> dict[str, Any]:
    if target_profile == "fastapi-sqlalchemy":
        test_file = generated_dir / "test_suite.py"
        if not test_file.exists():
            return {"status": "not_available", "reason": "test_suite.py was not generated"}
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", test_file.name],
            cwd=generated_dir, text=True, capture_output=True, env=environment, timeout=120, check=False,
        )
        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "return_code": result.returncode,
            "output": (result.stdout + result.stderr)[-4000:]
        }
    else:
        # Spring Boot test detection
        java_tests = list(generated_dir.rglob("*Test*.java"))
        if not java_tests:
            return {"status": "not_available", "reason": "No JUnit test classes generated"}
        return {"status": "present", "test_files": [str(t.relative_to(generated_dir)) for t in java_tests]}


def evaluate(source_dir: Path, generated_dir: Path, target_profile: str = "fastapi-sqlalchemy", run_tests: bool = False) -> dict[str, Any]:
    if not source_dir.is_dir() or not generated_dir.is_dir():
        raise ValueError("Both --source-dir and --generated-dir must be existing directories.")

    source_files = eligible_source_files(source_dir)
    expected_outputs = PROFILE_REQUIRED_OUTPUTS.get(target_profile, PROFILE_REQUIRED_OUTPUTS["fastapi-sqlalchemy"])

    # Locate missing artifacts (allowing nested matches for config files like application.properties)
    missing_outputs = []
    for expected in expected_outputs:
        found = any(p.name == expected or str(p.relative_to(generated_dir)).replace("\\", "/") == expected for p in generated_dir.rglob("*"))
        if not found:
            missing_outputs.append(expected)

    # Syntax checks tailored to target profile
    if "fastapi" in target_profile:
        target_files_count, syntax_failures = compile_python_files(generated_dir)
        syntax_metric_label = "python_files_checked"
    else:
        target_files_count, syntax_failures = check_java_syntax_and_structure(generated_dir)
        syntax_metric_label = "java_files_checked"

    test_result = run_generated_tests(generated_dir, target_profile) if run_tests else {"status": "not_run"}
    secret_findings = find_secret_leaks(generated_dir)
    fixture_acceptance = check_fixture_acceptance(source_dir, generated_dir, target_profile)

    metrics = {
        "target_profile": target_profile,
        "source_files_discovered": len(source_files),
        "required_artifacts_present": len(expected_outputs) - len(missing_outputs),
        "required_artifacts_expected": len(expected_outputs),
        "artifact_completeness_percent": round(100 * (len(expected_outputs) - len(missing_outputs)) / len(expected_outputs), 2),
        syntax_metric_label: target_files_count,
        "syntax_pass_rate_percent": round(100 * (target_files_count - len(syntax_failures)) / target_files_count, 2) if target_files_count else 0.0,
        "secret_leaks_detected": len(secret_findings),
        "fixture_acceptance_score_percent": fixture_acceptance["acceptance_score_percent"]
    }

    passed = not missing_outputs and not syntax_failures and not secret_findings and fixture_acceptance["passed"]
    if run_tests and "fastapi" in target_profile:
        passed = passed and test_result.get("status") == "passed"

    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "source_dir": str(source_dir),
        "generated_dir": str(generated_dir),
        "target_profile": target_profile,
        "passed": passed,
        "metrics": metrics,
        "missing_required_artifacts": missing_outputs,
        "syntax_failures": syntax_failures,
        "secret_findings": secret_findings,
        "fixture_acceptance": fixture_acceptance,
        "generated_test_result": test_result,
        "notes": [
            "Evaluated with profile-specific rules (target: " + target_profile + ").",
            "Zero LLM tokens consumed during evaluation."
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a generated Legacy Modernizer project.")
    parser.add_argument("--source-dir", type=Path, required=True, help="Directory of original legacy code")
    parser.add_argument("--generated-dir", type=Path, required=True, help="Directory of modernized project")
    parser.add_argument("--target-profile", choices=["fastapi-sqlalchemy", "spring-boot-jpa"], default="fastapi-sqlalchemy", help="Target stack profile")
    parser.add_argument("--run-tests", action="store_true", help="Execute generated tests")
    args = parser.parse_args()

    report = evaluate(args.source_dir.resolve(), args.generated_dir.resolve(), args.target_profile, args.run_tests)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / f"evaluation-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nSaved report: {report_path.relative_to(PROJECT_ROOT)}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
