import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    is_leader: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preferred_locale: Mapped[str] = mapped_column(
        String(10), default="en", nullable=False
    )
    # MS Graph API delegated token for Mail.Send (stored as opaque encrypted string in prod)
    ms_graph_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Profile picture stored as a base64 data URL (synced from MS365)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Local (non-SSO) login support — only the seeded admin account uses these
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_local_login: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # GitHub OAuth account linking — token stored AES-256-GCM encrypted at rest
    github_access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_token_iv: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
