"""Database engine, session factory, and schema initialisation."""

from pathlib import Path
from typing import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

# Store the SQLite file under backend/data/ so it's easy to back up (one file).
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "parts.db"

DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False is required because FastAPI may use the connection
# from a different thread than the one that created it.
engine = create_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record) -> None:
    """SQLite ignores foreign keys unless explicitly switched on per-connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    """Create tables if they don't exist yet."""
    # Import models so they register on SQLModel.metadata before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a session and closes it afterwards."""
    with Session(engine) as session:
        yield session
