import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import DB_PATH

# Setup SQLite database outside the repository in %LOCALAPPDATA%
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class JobRecord(Base):
    """Tracks each project modernization run in the database."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    project_name = Column(String(255), default="legacy_project")
    target_stack = Column(String(100), default="fastapi-sqlalchemy")
    status = Column(String(50), default="PENDING")  # UPLOADED, IN_PROGRESS, COMPLETED, FAILED
    progress_percent = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    logs = Column(Text, default="[]")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "project_name": self.project_name,
            "target_stack": self.target_stack,
            "status": self.status,
            "progress_percent": self.progress_percent,
            "total_files": self.total_files,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

# Automatically create tables in the external SQLite database
Base.metadata.create_all(bind=engine)

def get_db():
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
