"""API integration tests with TestClient."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api import app
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    r = client.post("/auth/token", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_fail(client):
    r = client.post("/auth/token", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_chat_requires_auth(client):
    r = client.post("/chat", json={"message": "hello"})
    assert r.status_code == 401


def test_stats_requires_auth(client):
    r = client.get("/stats")
    assert r.status_code == 401


def test_stats_with_token(client, admin_token):
    r = client.get("/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert "documents_indexed" in r.json()


def test_viewer_cannot_ingest(client):
    r = client.post("/auth/token", json={"username": "viewer", "password": "viewer123"})
    token = r.json()["access_token"]
    r = client.post(
        "/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("test.txt", b"hello", "text/plain"))],
    )
    assert r.status_code == 403
