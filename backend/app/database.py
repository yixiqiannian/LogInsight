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
        if "incident_id" not in columns:
            conn.execute(text("ALTER TABLE analysis_results ADD COLUMN incident_id INTEGER DEFAULT 0"))
            print("[DB] Added column: analysis_results.incident_id")
        if "is_incremental" not in columns:
            conn.execute(text("ALTER TABLE analysis_results ADD COLUMN is_incremental INTEGER DEFAULT 0"))
            print("[DB] Added column: analysis_results.is_incremental")

        wh_columns = [row[1] for row in conn.execute(text("PRAGMA table_info(webhook_configs)"))]
        if "push_severity" not in wh_columns:
            conn.execute(text("ALTER TABLE webhook_configs ADD COLUMN push_severity VARCHAR(20) DEFAULT 'p1p2'"))
            print("[DB] Added column: webhook_configs.push_severity")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_key VARCHAR(200),
                title VARCHAR(500) DEFAULT '',
                severity VARCHAR(20) DEFAULT 'medium',
                status VARCHAR(20) DEFAULT 'active',
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                log_count INTEGER DEFAULT 1,
                latest_analysis_id INTEGER DEFAULT 0,
                summary TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("[DB] Ensured table: incidents")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS system_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key VARCHAR(100) UNIQUE,
                config_value TEXT DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        print("[DB] Ensured table: system_configs")

        conn.commit()
