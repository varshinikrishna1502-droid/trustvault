import hashlib
import os
import uuid
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from access import can_access
from audit import log, verify_chain
from database import get_db
from models import AuditLog, Document, Permission, User, now
from security import current_user, require_role

router = APIRouter(prefix="/documents", tags=["documents"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}


def looks_valid(ext: str, content: bytes) -> bool:
    """Check the real file content, not only the extension."""
    if ext == ".pdf":
        return content.startswith(b"%PDF-")
    if ext == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return content.startswith(b"\xff\xd8\xff")
    if ext == ".txt":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return b"\x00" not in content
    return False


def clean_name(name: str) -> str:
    name = os.path.basename((name or "").replace("\\", "/"))
    return name[:100] or "file"


def get_doc_or_404(db, user, doc_id, access_action, audit_action):
    """The ONE place every document endpoint decides access."""
    doc = db.get(Document, doc_id)
    if doc is None or not can_access(db, user, doc, access_action):
        log(db, user.id, audit_action, doc_id, "denied")
        raise HTTPException(404, "Not found")  # 404 so existence is not leaked
    return doc


# ---------- Upload ----------
@router.post("", status_code=201)
async def upload(
    file: UploadFile = File(...),
    category: str = Form("general", max_length=50),
    user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db),
):
    name = clean_name(file.filename)
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED:
        log(db, user.id, "upload", None, "denied", f"bad type {ext}")
        raise HTTPException(400, "File type not allowed")
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(413, "File too large (max 5 MB)")
    if len(content) == 0 or not looks_valid(ext, content):
        log(db, user.id, "upload", None, "denied", "content does not match type")
        raise HTTPException(400, "File content does not match its type")

    key = uuid.uuid4().hex  # random name on disk, user input never used as a path
    with open(os.path.join(UPLOAD_DIR, key), "wb") as f:
        f.write(content)
    doc = Document(owner_id=user.id, name=name, category=category,
                   storage_key=key, sha256=hashlib.sha256(content).hexdigest(),
                   size=len(content))
    db.add(doc)
    db.commit()
    log(db, user.id, "upload", doc.id, "allowed", f"name={name}")
    return {"id": doc.id, "name": doc.name, "category": doc.category, "size": doc.size}


# ---------- List + Search (only documents the user can access) ----------
@router.get("")
def list_documents(
    q: Optional[str] = None,
    category: Optional[str] = None,
    owner: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    shared_ids = db.query(Permission.doc_id).filter(
        Permission.user_id == user.id, Permission.revoked_at.is_(None))
    query = (
        db.query(Document, User.email)
        .join(User, User.id == Document.owner_id)
        .filter(Document.deleted_at.is_(None),
                or_(Document.owner_id == user.id, Document.id.in_(shared_ids)))
    )
    if q:
        query = query.filter(Document.name.ilike(f"%{q}%"))
    if category:
        query = query.filter(Document.category == category)
    if owner:
        query = query.filter(User.email.ilike(f"%{owner}%"))
    if date_from:
        query = query.filter(Document.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(Document.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    return [
        {"id": d.id, "name": d.name, "category": d.category, "owner": email,
         "size": d.size, "created_at": d.created_at}
        for d, email in query.order_by(Document.id.desc()).all()
    ]


# ---------- Download ----------
@router.get("/{doc_id}/download")
def download(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = get_doc_or_404(db, user, doc_id, "read", "download")
    path = os.path.join(UPLOAD_DIR, doc.storage_key)
    if not os.path.isfile(path):
        raise HTTPException(404, "Not found")
    log(db, user.id, "download", doc.id, "allowed")
    return FileResponse(path, filename=doc.name, media_type="application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff"})


# ---------- Edit (rename / change category) ----------
class EditIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=50)


@router.put("/{doc_id}")
def edit(doc_id: int, body: EditIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = get_doc_or_404(db, user, doc_id, "edit", "edit")
    if body.name:
        doc.name = clean_name(body.name)
    if body.category:
        doc.category = body.category
    db.commit()
    log(db, user.id, "edit", doc.id, "allowed")
    return {"id": doc.id, "name": doc.name, "category": doc.category}


# ---------- Delete (soft delete, owner only) ----------
@router.delete("/{doc_id}")
def delete(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = get_doc_or_404(db, user, doc_id, "delete", "delete")
    doc.deleted_at = now()
    db.commit()
    log(db, user.id, "delete", doc.id, "allowed")
    return {"deleted": True}


# ---------- Share / Revoke (owner only) ----------
class ShareIn(BaseModel):
    email: str
    level: str = Field(pattern="^(read|edit)$")


@router.post("/{doc_id}/share")
def share(doc_id: int, body: ShareIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = get_doc_or_404(db, user, doc_id, "share", "permission_grant")
    target = db.query(User).filter_by(email=body.email.lower()).first()
    if target is None or target.id == user.id:
        raise HTTPException(400, "Invalid user")
    perm = db.query(Permission).filter_by(
        doc_id=doc.id, user_id=target.id, revoked_at=None).first()
    if perm:
        perm.level = body.level
    else:
        db.add(Permission(doc_id=doc.id, user_id=target.id, level=body.level, granted_by=user.id))
    db.commit()
    log(db, user.id, "permission_grant", doc.id, "allowed", f"to={target.id} level={body.level}")
    return {"shared_with": target.email, "level": body.level}


@router.delete("/{doc_id}/share/{target_id}")
def revoke(doc_id: int, target_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = get_doc_or_404(db, user, doc_id, "share", "permission_revoke")
    perms = db.query(Permission).filter_by(
        doc_id=doc.id, user_id=target_id, revoked_at=None).all()
    if not perms:
        raise HTTPException(404, "No active permission")
    for p in perms:
        p.revoked_at = now()
    db.commit()
    log(db, user.id, "permission_revoke", doc.id, "allowed", f"from={target_id}")
    return {"revoked": True}


# ---------- Admin: audit view ----------
@admin_router.get("/audit")
def audit_view(action: Optional[str] = None, doc_id: Optional[int] = None,
               limit: int = 100, admin: User = Depends(require_role("admin")),
               db: Session = Depends(get_db)):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if doc_id:
        query = query.filter(AuditLog.doc_id == doc_id)
    rows = query.order_by(AuditLog.id.desc()).limit(min(limit, 500)).all()
    return [{"id": r.id, "ts": r.ts, "actor_id": r.actor_id, "action": r.action,
             "doc_id": r.doc_id, "result": r.result, "detail": r.detail} for r in rows]


@admin_router.get("/audit/verify")
def audit_verify(admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    ok, bad_id = verify_chain(db)
    return {"intact": ok, "first_broken_row": bad_id}