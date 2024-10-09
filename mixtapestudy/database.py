import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import DateTime, Engine, String, Text, Uuid, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, mapped_column

from mixtapestudy.config import get_config

_database_engine = None


class UnexpectedDatabaseError(Exception):
    pass


def get_engine() -> Engine:
    global _database_engine  # noqa: PLW0603
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
            raise UnexpectedDatabaseError from error
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
        DateTime(timezone=True),
        default=datetime.now(tz=UTC),
        onupdate=datetime.now(tz=UTC),
    )
    created = mapped_column(DateTime(timezone=True), default=datetime.now(tz=UTC))


class User(CommonColumns):
    __tablename__ = "user"

    spotify_id = mapped_column(String(255), nullable=False, unique=True)
    email = mapped_column(String(255), nullable=False, unique=True)
    display_name = mapped_column(String(255), nullable=False)
    access_token = mapped_column(Text(), nullable=False)
    token_scope = mapped_column(String(255), nullable=False)
    token_expires = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_token = mapped_column(Text(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"User("
            f"{self.id=}, "
            f"{self.created=}, "
            f"{self.updated=}, "
            f"{self.spotify_id=}, "
            f"{self.display_name=}, "
            f"{self.email=}, "
            f"{self.token_expires=}, "
            f"{self.refresh_token=}"
            f")"
        )
