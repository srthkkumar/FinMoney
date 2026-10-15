"""
Storage layer for past simulation runs.

Uses SQLite by default so the project runs with zero setup. Because it's
built on SQLAlchemy, switching to PostgreSQL/MySQL for a "real" deployment
is a one-line change to DATABASE_URL -- no other code changes needed.
"""

import datetime
import json
import os

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Swap this for e.g. "postgresql://user:pass@host/dbname" in production.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./finlaxmi_planner.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    inputs_json = Column(Text)
    summary_json = Column(Text)


def init_db():
    Base.metadata.create_all(bind=engine)


def save_run(inputs: dict, summary: dict) -> int:
    db = SessionLocal()
    try:
        run = SimulationRun(
            inputs_json=json.dumps(inputs),
            summary_json=json.dumps(summary),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id
    finally:
        db.close()


def list_runs(limit: int = 20):
    db = SessionLocal()
    try:
        rows = (
            db.query(SimulationRun)
            .order_by(SimulationRun.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "inputs": json.loads(r.inputs_json),
                "summary": json.loads(r.summary_json),
            }
            for r in rows
        ]
    finally:
        db.close()
