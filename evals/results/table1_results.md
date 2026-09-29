
### Table 1. Comparative Performance of the Proposed System and Baseline Approaches

| Method | Pipeline Architecture | AST Syntax Validity (%) | Rule Preservation Rate (%) | Pytest Pass Rate (%) | Test Suite Idempotency (%) | Avg Modernization Time (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Manual Re-engineering [1]** | Human Developer | 98.50 | 91.20 | 88.40 | 85.00 | ~72,000 (20 hrs) |
| **Rule-based Transpiler [4]** | AST Regex / CST | 82.30 | 74.60 | 62.10 | 60.50 | 4.2 |
| **Direct Single-Prompt LLM (GPT-4o) [7]** | Monolithic Prompt | 78.40 | 69.80 | 58.30 | 51.20 | 68.5 |
| **Direct Single-Prompt LLM (Gemini 2.5) [10]** | Monolithic Prompt | 81.10 | 72.30 | 64.70 | 59.80 | 38.2 |
| **Vanilla Multi-Agent (No AST Guardrails) [15]** | Multi-Agent Baseline | 89.60 | 84.10 | 76.50 | 72.10 | 84.0 |
| **Proposed Staged Multi-Agent Pipeline + Guardrails** | **Staged Micro-Pipeline + AST Guardrails** | **100.00** | **100.00** | **89.23** | **89.23** | **46.3** |

#### Description:
> Table 1 presents a comparative evaluation of the proposed staged multi-agent modernization pipeline against traditional transpilers and monolithic LLM approaches across benchmark legacy projects. The proposed architecture achieves 100.00% AST syntax validity and a 89.23% automated pytest pass rate, outperforming single-prompt LLMs by over 30% in test reliability. By introducing staged micro-contracts (models -> schemas -> routers) alongside AST-level post-processing guardrails, the system eliminates runtime type errors and ensures 89.23% idempotent test execution while reducing modernization time to an average of 46.3 seconds per project.
