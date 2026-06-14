"""
Базовая конфигурация SQLAlchemy.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import logging
import os

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chemrep:password@localhost:5432/chemrep"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Prometheus metrics for DB pool
try:
    from prometheus_client import Gauge, Counter
    DB_POOL_CHECKEDOUT = Gauge('db_pool_checked_out', 'Number of connections checked out')
    DB_POOL_CHECKEDIN = Gauge('db_pool_checked_in', 'Number of connections in pool')
    DB_POOL_OVERFLOW = Gauge('db_pool_overflow', 'Number of connections overflow')
    DB_POOL_ERRORS = Counter('db_pool_errors_total', 'Database pool errors', ['error_type'])
    _HAS_DB_METRICS = True
except ImportError:
    _HAS_DB_METRICS = False


def _update_pool_metrics():
    """Update Prometheus gauges with current pool stats."""
    if not _HAS_DB_METRICS:
        return
    try:
        pool = engine.pool
        DB_POOL_CHECKEDOUT.set(pool.checkedout())
        DB_POOL_CHECKEDIN.set(pool.checkedin())
        DB_POOL_OVERFLOW.set(pool.overflow())
    except Exception:
        pass


if _HAS_DB_METRICS:
    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_conn, connection_rec, connection_proxy):
        _update_pool_metrics()

    @event.listens_for(engine, "checkin")
    def _on_checkin(dbapi_conn, connection_rec):
        _update_pool_metrics()

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, connection_record):
        _update_pool_metrics()


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency для FastAPI — открывает и закрывает сессию на каждый запрос."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        if _HAS_DB_METRICS:
            DB_POOL_ERRORS.labels(error_type="checkout").inc()
        db.rollback()
        raise
    finally:
        db.close()
