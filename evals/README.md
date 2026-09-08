# Modernization evaluation suite

This suite evaluates generated projects without calling an LLM, so results are reproducible and do not consume API quota.

| Metric | Meaning | Release target |
| --- | --- | --- |
| Source files discovered | Scannable legacy source/config files exist. | At least 1 |
| Artifact completeness | Required API, model, schema, database, requirements, and environment files exist. | 100% |
| Python syntax pass rate | Generated Python can be parsed. | 100% |
| Generated test result | The generated pytest suite runs successfully. | Pass |
| Secret leaks detected | Generated output has no likely embedded credentials. | 0 |

Run from the repository root:

```powershell
py evals\run_evals.py --source-dir test-fixtures\java --generated-dir path\to\generated-project
```

Add `--run-tests` after installing the generated project's dependencies. Each run writes a timestamped JSON report to `evals/results/`.

A pass is not proof of behavioral equivalence. The next evaluation improvement is fixture-specific acceptance tests that assert expected APIs, status codes, and database behavior.
