"""Engine and transaction boundaries; construction never connects to the database."""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class Database:
    def __init__(self, url: str) -> None:
        options = {"pool_pre_ping": True, "connect_args": {"connect_timeout": 10}}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                options["poolclass"] = StaticPool
        self.engine = create_engine(url, **options)
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine, "connect")
            def enable_foreign_keys(connection, _record):
                connection.execute("PRAGMA foreign_keys=ON")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def dispose(self) -> None:
        self.engine.dispose()
