from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models so Alembic autogenerate can discover them.
# Keep this list sorted alphabetically.
from app.db.models import (  # noqa: E402, F401
    absence,
    admin_settings,
    category,
    daily_record,
    notification,
    notification_preference,
    project,
    quarterly_report,
    social,
    task_entry,
    team,
    user,
    weekly_report,
)
