"""Ownership checks on uploads, share status, and chat conversation state.

Upload and conversation ids used to be enough on their own: anyone holding one
could download or delete the file, list a conversation's uploads, read its
share token, or have /chat pull its turn summaries and files into their own
prompt. Every path now checks the caller owns the conversation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from backend import db
from backend.auth import get_current_user, require_auth
from backend.main import _scope_to_caller, app
from backend.models import ChatRequest

OWNER = {"id": "user_a", "tier": "free"}
STRANGER = {"id": "user_b", "tier": "free"}


@pytest_asyncio.fixture
async def seeded(tmp_path):
    settings = MagicMock()
    settings.db_path = str(tmp_path / "test.db")
    settings.upload_dir = tmp_path / "uploads"
    with patch("backend.db.get_settings", return_value=settings):
        await db.init_db()
        await db.create_conversation("conv_a", "Owner's", user_id="user_a")
        stored = tmp_path / "plan.png"
        stored.write_bytes(b"png")
        await db.save_upload(
            upload_id="up_1", conversation_id="conv_a", filename="plan.png",
            mime_type="image/png", size_bytes=3, storage_path=str(stored),
        )
        yield stored
        await db.close_db()


@pytest.fixture
def as_user():
    """Run requests as a given user (None = anonymous), with CSRF off."""
    auth_settings = MagicMock()
    auth_settings.google_client_id = ""

    def _set(user: dict | None) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        if user is None:
            def _deny():
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail="Authentication required")
            app.dependency_overrides[require_auth] = _deny
        else:
            app.dependency_overrides[require_auth] = lambda: user
        return TestClient(app)

    with patch("backend.auth.get_settings", return_value=auth_settings):
        yield _set
    app.dependency_overrides.clear()


class TestUploadEndpoints:
    async def test_owner_can_download(self, seeded, as_user):
        assert as_user(OWNER).get("/api/uploads/up_1/file").status_code == 200

    @pytest.mark.parametrize("user", [None, STRANGER])
    async def test_others_cannot_download(self, seeded, as_user, user):
        assert as_user(user).get("/api/uploads/up_1/file").status_code == 404

    async def test_shared_conversation_attachments_are_readable(self, seeded, as_user):
        await db.create_share_token("conv_a", "user_a")
        assert as_user(None).get("/api/uploads/up_1/file").status_code == 200

    async def test_stranger_cannot_delete(self, seeded, as_user):
        assert as_user(STRANGER).delete("/api/uploads/up_1").status_code == 404
        assert seeded.exists()
        assert await db.get_upload("up_1") is not None

    async def test_share_does_not_grant_delete(self, seeded, as_user):
        await db.create_share_token("conv_a", "user_a")
        assert as_user(STRANGER).delete("/api/uploads/up_1").status_code == 404

    async def test_owner_can_delete(self, seeded, as_user):
        assert as_user(OWNER).delete("/api/uploads/up_1").status_code == 200
        assert not seeded.exists()

    async def test_anonymous_cannot_list_uploads(self, seeded, as_user):
        assert as_user(None).get("/api/conversations/conv_a/uploads").status_code == 401

    async def test_stranger_cannot_list_uploads(self, seeded, as_user):
        assert as_user(STRANGER).get("/api/conversations/conv_a/uploads").status_code == 404


class TestShareStatus:
    async def test_stranger_cannot_read_share_token(self, seeded, as_user):
        await db.create_share_token("conv_a", "user_a")
        resp = as_user(STRANGER).get("/api/conversations/conv_a/share")
        assert resp.status_code == 404

    async def test_owner_reads_share_token(self, seeded, as_user):
        await db.create_share_token("conv_a", "user_a")
        resp = as_user(OWNER).get("/api/conversations/conv_a/share")
        assert resp.json()["shared"] is True


class TestChatScoping:
    async def test_owner_keeps_conversation_and_uploads(self, seeded):
        req = ChatRequest(message="hi", conversation_id="conv_a", upload_ids=["up_1"])
        scoped = await _scope_to_caller(req, OWNER)
        assert scoped.conversation_id == "conv_a"
        assert scoped.upload_ids == ["up_1"]

    @pytest.mark.parametrize("user", [None, STRANGER])
    async def test_unowned_conversation_and_uploads_are_dropped(self, seeded, user):
        req = ChatRequest(message="hi", conversation_id="conv_a", upload_ids=["up_1"])
        scoped = await _scope_to_caller(req, user)
        assert scoped.conversation_id is None
        assert scoped.upload_ids == []

    async def test_upload_from_another_conversation_is_dropped(self, seeded):
        await db.create_conversation("conv_b", "Other", user_id="user_b")
        req = ChatRequest(message="hi", conversation_id="conv_b", upload_ids=["up_1"])
        scoped = await _scope_to_caller(req, STRANGER)
        assert scoped.conversation_id == "conv_b"
        assert scoped.upload_ids == []


class TestClearAll:
    async def test_clear_all_only_removes_the_callers_files(self, seeded, tmp_path):
        other_file = tmp_path / "other.png"
        other_file.write_bytes(b"png")
        await db.create_conversation("conv_b", "Other", user_id="user_b")
        await db.save_upload(
            upload_id="up_2", conversation_id="conv_b", filename="other.png",
            mime_type="image/png", size_bytes=3, storage_path=str(other_file),
        )
        await db.clear_all_conversations("user_b")
        assert not other_file.exists()
        assert seeded.exists()
        assert await db.get_upload("up_1") is not None
