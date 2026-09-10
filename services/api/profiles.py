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
            "cd /d \"%~dp0\"\r\n"
            "if not exist venv (\r\n"
            "    echo [1/3] Creating isolated virtual environment...\r\n"
            "    python -m venv venv\r\n"
            "    if errorlevel 1 (\r\n"
            "        echo Python not found in PATH. Please install Python 3.10+.\r\n"
            "        pause\r\n"
            "        exit /b 1\r\n"
            "    )\r\n"
            "    call venv\\Scripts\\activate.bat\r\n"
            "    echo [2/3] Installing dependencies from requirements.txt...\r\n"
            "    python -m pip install --upgrade pip --quiet\r\n"
            "    pip install -r requirements.txt\r\n"
            ") else (\r\n"
            "    call venv\\Scripts\\activate.bat\r\n"
            ")\r\n"
            "echo [3/3] Starting Modernized FastAPI Server on Port 8080...\r\n"
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
