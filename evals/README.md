# Modernization evaluation suite

This suite evaluates generated projects without calling an LLM, so results are reproducible and do not consume API quota.

| Metric | Meaning | Target |
| :--- | :--- | :--- |
| **Source files discovered** | Scannable legacy source/config files exist. | At least 1 |
| **Artifact completeness** | Profile-specific required files (FastAPI or Spring Boot) exist. | 100% |
| **Syntax pass rate** | Generated Python (AST) or Java files have valid syntax. | 100% |
| **Secret leaks detected** | Generated output contains 0 hardcoded credentials. | 0 |
| **Fixture acceptance** | Domain models (e.g. `User`), fields, and endpoints are preserved. | 100% |

### Running Evaluations

From the repository root:

#### 1. Evaluate Python Target (FastAPI + SQLAlchemy)
```powershell
python evals\run_evals.py --source-dir test-fixtures\java --generated-dir path\to\generated-project --target-profile fastapi-sqlalchemy
```

#### 2. Evaluate Java Target (Spring Boot 3 + JPA)
```powershell
python evals\run_evals.py --source-dir test-fixtures\java --generated-dir path\to\generated-project --target-profile spring-boot-jpa
```

Add `--run-tests` to execute generated integration tests. Each evaluation writes a timestamped JSON report to `evals/results/`.
