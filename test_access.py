from conftest import login, upload, user_id
from database import SessionLocal
from models import AuditLog


# ---------- 1. Strangers cannot reach a document ----------
def test_no_token_is_rejected(client, doc):
    assert client.get(f"/documents/{doc}/download").status_code in (401, 403)


def test_unshared_viewer_cannot_read_edit_delete_share(client, doc, viewer):
    assert client.get(f"/documents/{doc}/download", headers=viewer).status_code == 404
    assert client.put(f"/documents/{doc}", json={"name": "x.txt"}, headers=viewer).status_code == 404
    assert client.delete(f"/documents/{doc}", headers=viewer).status_code == 404
    r = client.post(f"/documents/{doc}/share", json={"email": "viewer@trustvault.com", "level": "edit"}, headers=viewer)
    assert r.status_code == 404


def test_other_owner_cannot_reach_my_document(client, doc, owner2):
    assert client.get(f"/documents/{doc}/download", headers=owner2).status_code == 404
    assert client.put(f"/documents/{doc}", json={"name": "x.txt"}, headers=owner2).status_code == 404
    assert client.delete(f"/documents/{doc}", headers=owner2).status_code == 404
    r = client.post(f"/documents/{doc}/share", json={"email": "owner2@test.com", "level": "edit"}, headers=owner2)
    assert r.status_code == 404


def test_admin_cannot_read_document_content(client, doc, admin):
    assert client.get(f"/documents/{doc}/download", headers=admin).status_code == 404


def test_nonexistent_and_forbidden_look_the_same(client, doc, viewer):
    a = client.get(f"/documents/{doc}/download", headers=viewer)
    b = client.get("/documents/999999/download", headers=viewer)
    assert a.status_code == b.status_code == 404
    assert a.json() == b.json()


# ---------- 2. Search and list do not leak ----------
def test_list_and_search_hide_unshared_documents(client, doc, owner, viewer):
    ids = [d["id"] for d in client.get("/documents", headers=viewer).json()]
    assert doc not in ids
    ids = [d["id"] for d in client.get("/documents?q=secret", headers=viewer).json()]
    assert doc not in ids
    ids = [d["id"] for d in client.get("/documents?q=secret", headers=owner).json()]
    assert doc in ids


# ---------- 3. Sharing levels ----------
def test_read_grant_allows_read_but_not_edit_delete_share(client, doc, owner, viewer):
    client.post(f"/documents/{doc}/share", json={"email": "viewer@trustvault.com", "level": "read"}, headers=owner)
    assert client.get(f"/documents/{doc}/download", headers=viewer).status_code == 200
    assert client.put(f"/documents/{doc}", json={"name": "x.txt"}, headers=viewer).status_code == 404
    assert client.delete(f"/documents/{doc}", headers=viewer).status_code == 404
    r = client.post(f"/documents/{doc}/share", json={"email": "owner2@test.com", "level": "read"}, headers=viewer)
    assert r.status_code == 404
    ids = [d["id"] for d in client.get("/documents", headers=viewer).json()]
    assert doc in ids


def test_edit_grant_allows_edit_but_not_delete(client, doc, owner, viewer):
    client.post(f"/documents/{doc}/share", json={"email": "viewer@trustvault.com", "level": "edit"}, headers=owner)
    assert client.put(f"/documents/{doc}", json={"name": "renamed.txt"}, headers=viewer).status_code == 200
    assert client.delete(f"/documents/{doc}", headers=viewer).status_code == 404


# ---------- 4. Revoke works immediately ----------
def test_revoke_stops_an_already_issued_token(client, doc, owner, viewer):
    viewer_id = user_id(client, viewer)
    client.post(f"/documents/{doc}/share", json={"email": "viewer@trustvault.com", "level": "read"}, headers=owner)
    assert client.get(f"/documents/{doc}/download", headers=viewer).status_code == 200
    r = client.delete(f"/documents/{doc}/share/{viewer_id}", headers=owner)
    assert r.status_code == 200
    # SAME token as before, no new login
    assert client.get(f"/documents/{doc}/download", headers=viewer).status_code == 404


def test_deleted_document_is_unreachable_even_when_shared(client, doc, owner, viewer):
    client.post(f"/documents/{doc}/share", json={"email": "viewer@trustvault.com", "level": "read"}, headers=owner)
    assert client.delete(f"/documents/{doc}", headers=owner).status_code == 200
    assert client.get(f"/documents/{doc}/download", headers=viewer).status_code == 404
    assert client.get(f"/documents/{doc}/download", headers=owner).status_code == 404


# ---------- 5. Roles and signup ----------
def test_signup_cannot_choose_a_role(client):
    r = client.post("/auth/signup", json={"email": "sneaky@test.com", "password": "Sneaky@12345", "role": "admin"})
    assert r.status_code == 201
    assert r.json()["role"] == "viewer"


def test_viewer_cannot_upload_or_use_admin_endpoints(client, viewer):
    assert upload(client, viewer).status_code == 403
    assert client.get("/admin/audit", headers=viewer).status_code == 403
    assert client.get("/admin/audit/verify", headers=viewer).status_code == 403
    assert client.put("/admin/users/1/role", json={"role": "admin"}, headers=viewer).status_code == 403


def test_role_change_kills_old_tokens(client, admin):
    r = client.post("/auth/signup", json={"email": "temp@test.com", "password": "Temp@12345"})
    uid = r.json()["id"]
    old = login(client, "temp@test.com", "Temp@12345")
    assert client.get("/auth/me", headers=old).status_code == 200
    client.put(f"/admin/users/{uid}/role", json={"role": "owner"}, headers=admin)
    assert client.get("/auth/me", headers=old).status_code == 401


# ---------- 6. Upload validation ----------
def test_bad_file_types_are_rejected(client, owner):
    assert upload(client, owner, name="virus.exe", content=b"MZ....").status_code == 400
    assert upload(client, owner, name="page.html", content=b"<script>alert(1)</script>").status_code == 400
    assert upload(client, owner, name="fake.pdf", content=b"this is not a pdf").status_code == 400
    assert upload(client, owner, name="empty.txt", content=b"").status_code == 400


def test_too_large_file_is_rejected(client, owner):
    assert upload(client, owner, name="big.txt", content=b"a" * (5 * 1024 * 1024 + 10)).status_code == 413


def test_path_traversal_filename_is_neutralised(client, owner):
    r = upload(client, owner, name="../../evil.txt", content=b"hello")
    assert r.status_code == 201
    assert r.json()["name"] == "evil.txt"


# ---------- 7. Audit trail ----------
def test_denied_attempts_are_recorded(client, doc, viewer, admin):
    viewer_id = user_id(client, viewer)
    client.get(f"/documents/{doc}/download", headers=viewer)
    rows = client.get(f"/admin/audit?doc_id={doc}&action=download", headers=admin).json()
    assert any(r["result"] == "denied" and r["actor_id"] == viewer_id for r in rows)


def test_grant_and_revoke_are_recorded(client, doc, owner, viewer, admin):
    viewer_id = user_id(client, viewer)
    client.post(f"/documents/{doc}/share", json={"email": "viewer@trustvault.com", "level": "read"}, headers=owner)
    client.delete(f"/documents/{doc}/share/{viewer_id}", headers=owner)
    actions = [r["action"] for r in client.get(f"/admin/audit?doc_id={doc}", headers=admin).json()]
    assert "permission_grant" in actions
    assert "permission_revoke" in actions


def test_audit_chain_detects_tampering(client, doc, admin):
    assert client.get("/admin/audit/verify", headers=admin).json()["intact"] is True
    db = SessionLocal()
    try:
        row = db.query(AuditLog).filter(AuditLog.doc_id == doc).first()
        original = row.result
        row.result = "allowed" if original == "denied" else "denied"
        db.commit()
        verdict = client.get("/admin/audit/verify", headers=admin).json()
        assert verdict["intact"] is False
        row.result = original  # put it back so other tests keep working
        db.commit()
    finally:
        db.close()
    assert client.get("/admin/audit/verify", headers=admin).json()["intact"] is True
def test_role_change_is_audited(client, admin):
    r = client.post("/auth/signup", json={"email": "audit-me@test.com", "password": "Audit@12345"})
    uid = r.json()["id"]
    client.put(f"/admin/users/{uid}/role", json={"role": "owner"}, headers=admin)
    rows = client.get("/admin/audit?action=role_change", headers=admin).json()
    assert any(f"user={uid} " in row["detail"] for row in rows)