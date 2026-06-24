from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    with engine.connect() as conn:
        columns = [row[1] for row in conn.execute(text("PRAGMA table_info(analysis_results)"))]
        if "impact_scope" not in columns:
            conn.execute(text("ALTER TABLE analysis_results ADD COLUMN impact_scope TEXT DEFAULT ''"))
            print("[DB] Added column: impact_scope")
        if "troubleshooting_commands" not in columns:
            conn.execute(text("ALTER TABLE analysis_results ADD COLUMN troubleshooting_commands TEXT DEFAULT ''"))
            print("[DB] Added column: troubleshooting_commands")
        conn.commit()
