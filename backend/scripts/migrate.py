"""
Controlled Database Migration and Health Validation Runner for BhumiSetu.
Usage:
    python -m scripts.migrate [upgrade|downgrade <rev>|check]
"""
import os
import sys
import time
import argparse
import logging
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
import sqlalchemy as sa

# Ensure backend root is on path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings
from app.core.logging_config import setup_logging

setup_logging(settings.ENVIRONMENT)
logger = logging.getLogger("bhumisetu.migrate")


def get_alembic_config() -> Config:
    ini_path = os.path.join(backend_dir, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return cfg


def wait_for_database(max_retries: int = 15, delay: float = 2.0) -> bool:
    """Waits for target database to become reachable."""
    logger.info(f"Checking database connectivity: {settings.DATABASE_URL.split('@')[-1]}")
    for attempt in range(1, max_retries + 1):
        try:
            engine = sa.create_engine(settings.DATABASE_URL, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))
            logger.info("Database connection established successfully.")
            return True
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}")
            time.sleep(delay)
    return False


def get_migration_status(cfg: Config):
    """Retrieves current and head revision identifiers."""
    script = ScriptDirectory.from_config(cfg)
    head_rev = script.get_current_head()

    engine = sa.create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()

    return current_rev, head_rev


def run_upgrade(cfg: Config):
    """Executes migration up to head revision."""
    current_rev, head_rev = get_migration_status(cfg)
    logger.info(f"Current migration revision: {current_rev} | Head revision: {head_rev}")

    if current_rev == head_rev and head_rev is not None:
        logger.info("Database is already up-to-date with head revision.")
        return 0

    logger.info("Applying database migrations to head...")
    command.upgrade(cfg, "head")
    
    new_rev, _ = get_migration_status(cfg)
    logger.info(f"Migration completed. Active revision is now: {new_rev}")
    return 0


def run_downgrade(cfg: Config, target_rev: str):
    """Executes migration rollback to target revision."""
    current_rev, _ = get_migration_status(cfg)
    logger.warning(f"Executing migration downgrade from {current_rev} to {target_rev}...")
    command.downgrade(cfg, target_rev)
    new_rev, _ = get_migration_status(cfg)
    logger.info(f"Downgrade completed. Active revision is now: {new_rev}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="BhumiSetu Controlled Migration Runner")
    parser.add_argument("action", choices=["upgrade", "downgrade", "check"], default="upgrade", nargs="?")
    parser.add_argument("--target", default="base", help="Target revision for downgrade (default: base)")
    args = parser.parse_args()

    cfg = get_alembic_config()

    if not wait_for_database():
        logger.error("Database unavailable. Aborting migration.")
        sys.exit(1)

    if args.action == "check":
        current_rev, head_rev = get_migration_status(cfg)
        logger.info(f"Status check - Current: {current_rev}, Head: {head_rev}")
        sys.exit(0 if current_rev == head_rev else 2)
    elif args.action == "upgrade":
        sys.exit(run_upgrade(cfg))
    elif args.action == "downgrade":
        sys.exit(run_downgrade(cfg, args.target))


if __name__ == "__main__":
    main()
