from logging.config import fileConfig
import sqlalchemy as sa
from alembic import context

from app.config import settings
from app.database import Base
import app.models  # Ensure all models are registered with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_database_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    if "sqlalchemy.url" in x_args:
        return x_args["sqlalchemy.url"]
    if "db_url" in x_args:
        return x_args["db_url"]
    url = config.get_main_option("sqlalchemy.url")
    if url and not url.startswith("driver://"):
        return url
    return settings.DATABASE_URL

def run_migrations_offline() -> None:
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    db_url = get_database_url()
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    connectable = sa.create_engine(
        db_url,
        connect_args=connect_args,
        poolclass=sa.pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            if connection.dialect.name == "postgresql":
                connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                connection.execute(sa.text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"))
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
