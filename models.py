from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from database import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")  # admin | owner | viewer
    token_version = Column(Integer, default=0)


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, default="general")
    storage_key = Column(String, nullable=False)  # random file name on disk
    sha256 = Column(String)
    size = Column(Integer)
    created_at = Column(DateTime, default=now)
    deleted_at = Column(DateTime, nullable=True)


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    level = Column(String, nullable=False)  # read | edit
    granted_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=now)
    revoked_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    ts = Column(String, nullable=False)
    actor_id = Column(Integer)
    action = Column(String, nullable=False)
    doc_id = Column(Integer)
    result = Column(String, nullable=False)  # allowed | denied
    detail = Column(String, default="")
    prev_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False)