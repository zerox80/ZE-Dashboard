import os
from sqlmodel import SQLModel, create_engine, Session

sqlite_url = os.getenv("DATABASE_URL", "sqlite:///./ze_dashboard.db")
debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=debug_mode, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
