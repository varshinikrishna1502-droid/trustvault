import hashlib
import hmac
import os
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import AuditLog
from security import SECRET

GENESIS = "0" * 64
_KEY = (os.environ.get("AUDIT_KEY") or SECRET).encode()
_lock = threading.Lock()


def compute_hash(prev, ts, actor, action, doc_id, result, detail):
    text = f"{prev}|{ts}|{actor}|{action}|{doc_id}|{result}|{detail}"
    return hmac.new(_KEY, text.encode(), hashlib.sha256).hexdigest()


def log(db: Session, actor_id, action, doc_id, result, detail=""):
    with _lock:  # one writer at a time, so the chain cannot fork
        last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        prev = last.hash if last else GENESIS
        ts = datetime.now(timezone.utc).isoformat()
        h = compute_hash(prev, ts, actor_id, action, doc_id, result, detail)
        db.add(AuditLog(ts=ts, actor_id=actor_id, action=action, doc_id=doc_id,
                        result=result, detail=detail, prev_hash=prev, hash=h))
        db.commit()


def verify_chain(db: Session):
    prev = GENESIS
    for row in db.query(AuditLog).order_by(AuditLog.id).all():
        expected = compute_hash(prev, row.ts, row.actor_id, row.action,
                                row.doc_id, row.result, row.detail)
        if row.prev_hash != prev or row.hash != expected:
            return False, row.id
        prev = row.hash
    return True, None