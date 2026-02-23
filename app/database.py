import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Support both DATABASE_URL (local) and POSTGRES_URI (Zeabur auto-injected)
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URI")
)

if not DATABASE_URL:
    raise RuntimeError("No database URL found. Set DATABASE_URL in .env")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
