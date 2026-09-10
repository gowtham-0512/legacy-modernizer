"""Modern Tech Detector Engine for Legacy Modernizer V2.

Inspects source code, dependencies, and configuration files in an uploaded project bundle
to determine if the codebase already uses modern architectures (e.g. FastAPI, SQLAlchemy 2.0,
Spring Boot 3, React, Next.js) before running AI modernization agents.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


# Modern framework signature patterns
MODERN_FRAMEWORK_SIGNATURES = {
    "FastAPI": {
        "patterns": [
            re.compile(r"\bfrom\s+fastapi\s+import\b"),
            re.compile(r"\bimport\s+fastapi\b"),
            re.compile(r"@app\.(get|post|put|delete|patch|options)\("),
        ],
        "category": "backend",
        "stack": "fastapi-sqlalchemy",
    },
    "SQLAlchemy 2.0+": {
        "patterns": [
            re.compile(r"\bfrom\s+sqlalchemy\.orm\s+import\s+.*DeclarativeBase\b"),
            re.compile(r"\bMapped\["),
            re.compile(r"\bmapped_column\("),
        ],
        "category": "database",
        "stack": "fastapi-sqlalchemy",
    },
    "Pydantic v2": {
        "patterns": [
            re.compile(r"\bfrom\s+pydantic\s+import\s+BaseModel\b"),
            re.compile(r"\bmodel_dump\("),
            re.compile(r"\bfield_validator\("),
        ],
        "category": "schema",
        "stack": "fastapi-sqlalchemy",
    },
    "Spring Boot 3+": {
        "patterns": [
            re.compile(r"\bimport\s+jakarta\.persistence\."),
            re.compile(r"\bimport\s+jakarta\.servlet\."),
            re.compile(r"spring-boot-starter-web"),
            re.compile(r"<artifactId>spring-boot-starter-data-jpa</artifactId>"),
        ],
        "category": "backend",
        "stack": "spring-boot-jpa",
    },
    "React": {
        "patterns": [
            re.compile(r"import\s+React\b"),
            re.compile(r"from\s+['\"]react['\"]"),
            re.compile(r"['\"]react['\"]\s*:\s*['\"][^'\"]+['\"]"),
        ],
        "category": "frontend",
        "stack": None,
    },
    "Next.js": {
        "patterns": [
            re.compile(r"from\s+['\"]next/(navigation|router|link|image)['\"]"),
            re.compile(r"['\"]next['\"]\s*:\s*['\"][^'\"]+['\"]"),
        ],
        "category": "frontend",
        "stack": None,
    },
    "Vue.js": {
        "patterns": [
            re.compile(r"from\s+['\"]vue['\"]"),
            re.compile(r"<script\s+setup"),
            re.compile(r"defineComponent\("),
        ],
        "category": "frontend",
        "stack": None,
    },
    "Tailwind CSS": {
        "patterns": [
            re.compile(r"@tailwind\s+(base|components|utilities)"),
            re.compile(r"tailwindcss"),
        ],
        "category": "frontend",
        "stack": None,
    },
}

# Legacy architecture patterns
LEGACY_SIGNATURES = {
    "Java EE javax.servlet": [
        re.compile(r"\bimport\s+javax\.servlet\."),
        re.compile(r"\bextends\s+HttpServlet\b"),
    ],
    "Raw JDBC DriverManager": [
        re.compile(r"DriverManager\.getConnection\("),
        re.compile(r"\bjava\.sql\.(PreparedStatement|Statement|ResultSet)\b"),
    ],
    "Legacy web.xml Servlet Mappings": [
        re.compile(r"<servlet-class>"),
        re.compile(r"<servlet-mapping>"),
    ],
    "JSP Scriptlets": [
        re.compile(r"<%\s*(?:@|=)?"),
    ],
    "Apache Struts": [
        re.compile(r"org\.apache\.struts"),
    ],
}


def detect_modern_tech(project_bundle: Dict[str, str], target_stack: str = "fastapi-sqlalchemy") -> Dict[str, Any]:
    """
    Analyzes project files for modern frameworks vs legacy patterns.
    
    Returns a structured verdict including:
    - is_already_modern (bool)
    - already_matches_target (bool)
    - detected_modern_frameworks (list)
    - detected_legacy_indicators (list)
    - recommendation (str)
    """
    detected_modern: Dict[str, List[str]] = {}
    matched_target_tech: List[str] = []
    detected_legacy: Dict[str, List[str]] = {}

    for file_path, content in project_bundle.items():
        # Check modern signatures
        for framework, config in MODERN_FRAMEWORK_SIGNATURES.items():
            for pat in config["patterns"]:
                if pat.search(content):
                    if framework not in detected_modern:
                        detected_modern[framework] = []
                    if file_path not in detected_modern[framework]:
                        detected_modern[framework].append(file_path)
                    if config["stack"] == target_stack and framework not in matched_target_tech:
                        matched_target_tech.append(framework)
                    break

        # Check legacy signatures
        for legacy_name, patterns in LEGACY_SIGNATURES.items():
            for pat in patterns:
                if pat.search(content):
                    if legacy_name not in detected_legacy:
                        detected_legacy[legacy_name] = []
                    if file_path not in detected_legacy[legacy_name]:
                        detected_legacy[legacy_name].append(file_path)
                    break

    # Determine backend classification
    has_legacy_backend = any(
        k in detected_legacy for k in ("Java EE javax.servlet", "Raw JDBC DriverManager", "Legacy web.xml Servlet Mappings", "Apache Struts")
    )
    
    # Modern backend detection
    has_modern_fastapi = "FastAPI" in detected_modern
    has_modern_spring = "Spring Boot 3+" in detected_modern
    is_modern_backend = (has_modern_fastapi or has_modern_spring) and not has_legacy_backend

    # Check whether the project already matches the requested target stack
    already_matches_target = False
    if target_stack == "fastapi-sqlalchemy" and has_modern_fastapi and not has_legacy_backend:
        already_matches_target = True
    elif target_stack == "spring-boot-jpa" and has_modern_spring and not has_legacy_backend:
        already_matches_target = True

    # Frontend breakdown
    has_modern_frontend = any(
        k in detected_modern for k in ("React", "Next.js", "Vue.js", "Tailwind CSS")
    )
    has_legacy_frontend = "JSP Scriptlets" in detected_legacy

    # Global verdict
    is_already_modern = already_matches_target or (is_modern_backend and not has_legacy_backend)

    # Formulate human-readable recommendation
    if already_matches_target:
        tech_str = ", ".join(matched_target_tech)
        recommendation = (
            f"This codebase is already built using the selected target stack ({target_stack}: {tech_str}). "
            "AI modernization is not required and has been safely skipped to preserve your clean architecture. "
            "Use 'Force Modernize' if you explicitly wish to re-scaffold the project."
        )
    elif is_modern_backend and not has_legacy_backend:
        frameworks_str = ", ".join(detected_modern.keys())
        recommendation = (
            f"Modern architecture detected ({frameworks_str}). If you wish to migrate to {target_stack}, "
            "this will perform a cross-stack migration."
        )
    elif has_legacy_backend and has_modern_frontend:
        recommendation = (
            "Hybrid codebase detected: Legacy backend (Java/JDBC/Servlets) paired with a modern frontend. "
            f"Modernizing backend to {target_stack} while preserving your existing frontend."
        )
    else:
        recommendation = (
            f"Legacy architecture detected. Ready for automated modernization to {target_stack}."
        )

    # Markdown audit summary
    summary_lines = [
        "# Modern Architecture Pre-Flight Audit",
        f"- **Selected Target Stack**: `{target_stack}`",
        f"- **Already Modern**: `{'Yes' if is_already_modern else 'No'}`",
        f"- **Matches Target Architecture**: `{'Yes' if already_matches_target else 'No'}`",
        f"- **Backend Status**: `{'MODERN' if is_modern_backend else ('LEGACY' if has_legacy_backend else 'UNDETERMINED')}`",
        f"- **Frontend Status**: `{'MODERN' if has_modern_frontend else ('LEGACY' if has_legacy_frontend else 'N/A')}`",
        "",
        "### Detected Technologies",
    ]

    if detected_modern:
        summary_lines.append("**Modern Frameworks:**")
        for fw, files in detected_modern.items():
            summary_lines.append(f"- **{fw}** (found in `{', '.join(files[:3])}`)")
    else:
        summary_lines.append("- No modern frameworks detected.")

    if detected_legacy:
        summary_lines.append("\n**Legacy Indicators:**")
        for leg, files in detected_legacy.items():
            summary_lines.append(f"- **{leg}** (found in `{', '.join(files[:3])}`)")

    summary_lines.append(f"\n### Recommendation\n{recommendation}")

    return {
        "is_already_modern": is_already_modern,
        "already_matches_target": already_matches_target,
        "is_modern_backend": is_modern_backend,
        "has_legacy_backend": has_legacy_backend,
        "has_modern_frontend": has_modern_frontend,
        "detected_modern_frameworks": list(detected_modern.keys()),
        "detected_legacy_indicators": list(detected_legacy.keys()),
        "matched_target_frameworks": matched_target_tech,
        "recommendation": recommendation,
        "audit_markdown": "\n".join(summary_lines),
    }