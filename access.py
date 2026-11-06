from sqlalchemy.orm import Session

from models import Document, Permission, User


def can_access(db: Session, user: User, doc: Document, action: str) -> bool:
    """action: read | edit | delete | share"""
    if doc is None or doc.deleted_at is not None:
        return False
    if doc.owner_id == user.id:
        return True
    if action in ("delete", "share"):
        return False  # only the owner can delete or share
    perm = db.query(Permission).filter_by(
        doc_id=doc.id, user_id=user.id, revoked_at=None).first()
    if perm is None:
        return False
    if action == "read":
        return True
    if action == "edit":
        return perm.level == "edit"
    return False