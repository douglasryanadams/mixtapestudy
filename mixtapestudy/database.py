import logging
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, UTC

from sqlalchemy import create_engine, Engine, String, DateTime, Uuid
from sqlalchemy.orm import Session, DeclarativeBase, mapped_column

from mixtapestudy.env import get_config

logger = logging.getLogger(__name__)

_database_engine = None


def get_engine() -> Engine:
    global _database_engine
    if not _database_engine:
        config = get_config()
        _database_engine = create_engine(config.database_url)
    return _database_engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        try:
            yield session
        except Exception as error:
            session.rollback()
            raise error
        else:
            session.commit()


class Base(DeclarativeBase):
    pass


class CommonColumns(Base):
    __abstract__ = True

    id = mapped_column(
        Uuid(),
        primary_key=True,
        default=uuid.uuid4(),
        nullable=False,
        autoincrement=False,
    )
    updated = mapped_column(
        DateTime(), default=datetime.now(tz=UTC), onupdate=datetime.now(tz=UTC)
    )
    created = mapped_column(DateTime(), default=datetime.now(tz=UTC))


class User(CommonColumns):
    __tablename__ = "user"

    spotify_id = mapped_column(String(255), nullable=False)
    display_name = mapped_column(String(255), nullable=False)
    email = mapped_column(String(255), nullable=False)
    access_token = mapped_column(String(255), nullable=False)
    token_scope = mapped_column(String(255), nullable=False)
    refresh_token = mapped_column(String(255), nullable=False)

    def __repr__(self):
        return f"User({self.id=}, {self.created=}, {self.updated=}, {self.spotify_id=}, {self.display_name=}, {self.email=}, {self.refresh_token=})"
