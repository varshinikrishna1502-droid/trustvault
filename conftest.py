import os
import tempfile

# Use a throwaway database and upload folder for tests
_tmp = tempfile.mkdtemp().replace("\\", "/")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # runs startup: creates tables and seeds users
        yield c


def login(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def admin(client):
    return login(client, "admin@trustvault.com", "Admin@12345")


@pytest.fixture()
def owner(client):
    return login(client, "owner@trustvault.com", "Owner@12345")


@pytest.fixture()
def viewer(client):
    return login(client, "viewer@trustvault.com", "Viewer@12345")


@pytest.fixture(scope="session")
def owner2(client):
    """A second owner, to prove one owner cannot touch another owner's files."""
    r = client.post("/auth/signup", json={"email": "owner2@test.com", "password": "Owner2@12345"})
    assert r.status_code == 201
    uid = r.json()["id"]
    admin_h = login(client, "admin@trustvault.com", "Admin@12345")
    r = client.put(f"/admin/users/{uid}/role", json={"role": "owner"}, headers=admin_h)
    assert r.status_code == 200
    return login(client, "owner2@test.com", "Owner2@12345")


def upload(client, headers, name="secret.txt", content=b"top secret", category="hr"):
    return client.post("/documents", headers=headers,
                       files={"file": (name, content, "text/plain")},
                       data={"category": category})


@pytest.fixture()
def doc(client, owner):
    """A fresh document owned by owner@trustvault.com."""
    r = upload(client, owner)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def user_id(client, headers):
    return client.get("/auth/me", headers=headers).json()["id"]