import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

# psycopg 3 driver for SQLAlchemy
SQLALCHEMY_DATABASE_URL = DATABASE_URL.replace(
    "postgresql://",
    "postgresql+psycopg://",
    1,
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass
