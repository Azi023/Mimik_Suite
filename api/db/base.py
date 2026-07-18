"""SQLAlchemy declarative base. Models stay portable (String ids, JSON columns, tz-aware
datetimes) so tests run on SQLite while production runs on Postgres."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
