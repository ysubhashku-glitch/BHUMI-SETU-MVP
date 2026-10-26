import os
from typing import Generator
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.types import TypeDecorator, Text
from geoalchemy2 import Geometry
from app.config import settings

# Create engine with production-ready connection pool
if settings.DATABASE_URL.startswith("sqlite"):
    engine = sa.create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
else:
    engine = sa.create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True
    )

# Enable Foreign Key support for SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    @sa.event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class CompatibleGeometry(TypeDecorator):
    """
    Geometry TypeDecorator that natively maps to PostGIS Geometry on PostgreSQL,
    and falls back to WKT/Text on SQLite for headless test execution.
    """
    impl = Text
    cache_ok = True

    def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326, spatial_index: bool = True, **kwargs):
        super().__init__()
        self.geometry_type = geometry_type
        self.srid = srid
        self.spatial_index = spatial_index
        self.kwargs = kwargs

    def load_dialect_impl(self, dialect):
        if dialect is not None and dialect.name == "postgresql":
            return dialect.type_descriptor(Geometry(
                geometry_type=self.geometry_type,
                srid=self.srid,
                spatial_index=self.spatial_index,
                **self.kwargs
            ))
        elif dialect is not None:
            return dialect.type_descriptor(Text())
        return Text()

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return str(value)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
