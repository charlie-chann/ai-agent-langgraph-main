"""Conversation store unit tests (SQLite backend, no Postgres required)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def client(monkeypatch, tmp_path):
    db = tmp_path / "conv.db"
    monkeypatch.setenv("CONVERSATIONS_BACKEND", "sqlite")
    monkeypatch.setenv("CONVERSATIONS_SQLITE_PATH", str(db))
    from config import settings
    from app.infrastructure.persistence import conversations as conv_mod

    settings.conversations_backend = "sqlite"
    settings.conversations_sqlite_path = db
    conv_mod.reset_conversation_store()
    from main import app
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    r = client.post("/auth/token", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(autouse=True)
def fresh_store(tmp_path, monkeypatch):
    db = tmp_path / "conv.db"
    monkeypatch.setenv("CONVERSATIONS_BACKEND", "sqlite")
    monkeypatch.setenv("CONVERSATIONS_SQLITE_PATH", str(db))
    from config import settings
    from app.infrastructure.persistence import conversations as conv_mod

    settings.conversations_backend = "sqlite"
    settings.conversations_sqlite_path = db
    conv_mod.reset_conversation_store()
    store = conv_mod.get_conversation_store()
    store.setup()
    yield store
    conv_mod.reset_conversation_store()


def test_create_and_list_conversations(fresh_store):
    conv = fresh_store.create_conversation("alice", title="HR policy")
    assert conv["conversation_id"]
    listed = fresh_store.list_conversations("alice")
    assert len(listed) == 1
    assert listed[0]["title"] == "HR policy"


def test_append_and_load_messages(fresh_store):
    conv = fresh_store.create_conversation("bob")
    cid = conv["conversation_id"]
    fresh_store.append_message(cid, "user", "hello")
    fresh_store.append_message(cid, "assistant", "hi there")
    msgs = fresh_store.list_messages(cid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "hi there"


def test_user_isolation(fresh_store):
    conv = fresh_store.create_conversation("user_a")
    cid = conv["conversation_id"]
    assert fresh_store.get_conversation(cid, "user_a")
    assert fresh_store.get_conversation(cid, "user_b") is None


def test_api_conversation_endpoints(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    r = client.post("/conversations", json={"title": "test"}, headers=headers)
    assert r.status_code == 200
    cid = r.json()["conversation_id"]

    r2 = client.get(f"/conversations/{cid}/messages", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["messages"] == []

    r3 = client.get("/conversations", headers=headers)
    assert r3.status_code == 200
    assert any(c["conversation_id"] == cid for c in r3.json()["conversations"])
