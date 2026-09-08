from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
from pathlib import Path

# Setup the SQLite database file
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQLALCHEMY_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'modernizer.db'}"

# Create the SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Define our Database Table
class ProjectRecord(Base):
    __tablename__ = "project_history"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String, index=True)
    total_files = Column(Integer)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Create the tables in the database automatically
Base.metadata.create_all(bind=engine)
