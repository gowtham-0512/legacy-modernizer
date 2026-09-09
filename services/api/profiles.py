from typing import Dict, Any, List

TARGET_PROFILES: Dict[str, Dict[str, Any]] = {
    "fastapi-sqlalchemy": {
        "id": "fastapi-sqlalchemy",
        "name": "Python: FastAPI + SQLAlchemy 2.0 (Default)",
        "description": "Modern async Python full-stack with SQLAlchemy 2.0 ORM, Pydantic v2 schemas, and responsive HTML5/Tailwind SPA.",
        "backend": "FastAPI (Python 3.12+)",
        "database_layer": "SQLAlchemy 2.0 + MySQL / SQLite",
        "frontend": "Modern Responsive HTML5 / Tailwind SPA",
        "required_files": [
            "main.py",
            "database.py",
            "models.py",
            "schemas.py",
            "requirements.txt",
            ".env.example"
        ],
        "test_runner": "pytest",
        "run_command": "python -m uvicorn main:app --port 8080 --reload",
        "run_script_content": (
            "@echo off\r\n"
            "title Modernized FastAPI Application\r\n"
            "echo Starting Modernized FastAPI Server on Port 8080...\r\n"
            "start http://localhost:8080\r\n"
            "python -m uvicorn main:app --port 8080 --reload\r\n"
            "pause\r\n"
        )
    },
    "spring-boot-jpa": {
        "id": "spring-boot-jpa",
        "name": "Java: Spring Boot 3 + Spring Data JPA",
        "description": "Enterprise Java modernization targeting Spring Boot 3.x, Spring Data JPA, Hibernate, Maven, and modern REST APIs.",
        "backend": "Spring Boot 3.x (Java 17/21)",
        "database_layer": "Spring Data JPA + MySQL / H2",
        "frontend": "Modern REST Web Dashboard",
        "required_files": [
            "pom.xml",
            "src/main/resources/application.properties",
            "src/main/java/com/modernized/app/Application.java"
        ],
        "test_runner": "mvn test",
        "run_command": "mvn spring-boot:run",
        "run_script_content": (
            "@echo off\r\n"
            "title Modernized Spring Boot Application\r\n"
            "echo Starting Modernized Spring Boot Application on Port 8080...\r\n"
            "start http://localhost:8080\r\n"
            "mvn spring-boot:run\r\n"
            "pause\r\n"
        )
    }
}

def get_profile(profile_id: str) -> Dict[str, Any]:
    """Retrieves a target profile by ID, defaulting to fastapi-sqlalchemy if not found."""
    return TARGET_PROFILES.get(profile_id, TARGET_PROFILES["fastapi-sqlalchemy"])

def list_profiles() -> List[Dict[str, Any]]:
    """Returns list of all available target profiles for UI selectors and API clients."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "backend": p["backend"],
            "database_layer": p["database_layer"],
            "frontend": p["frontend"]
        }
        for p in TARGET_PROFILES.values()
    ]
