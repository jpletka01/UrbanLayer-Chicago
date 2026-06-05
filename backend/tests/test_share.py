"""Tests for conversation sharing."""

import pytest
import pytest_asyncio

from backend import db


@pytest_asyncio.fixture
async def test_db(tmp_path):
    from unittest.mock import patch, MagicMock

    mock_settings = MagicMock()
    mock_settings.db_path = str(tmp_path / "test.db")

    with patch("backend.db.get_settings", return_value=mock_settings):
        await db.init_db()
        yield
        await db.close_db()


@pytest.mark.asyncio
class TestConversationSharing:
    async def test_create_share_token(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        result = await db.create_share_token("conv_1", "user_a")
        assert result["token"]
        assert result["conversation_id"] == "conv_1"
        assert result["created_at"] > 0

    async def test_create_share_wrong_user(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        result = await db.create_share_token("conv_1", "user_b")
        assert result == {}

    async def test_create_share_nonexistent_conversation(self, test_db):
        result = await db.create_share_token("nope", "user_a")
        assert result == {}

    async def test_create_share_replaces_existing(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        first = await db.create_share_token("conv_1", "user_a")
        second = await db.create_share_token("conv_1", "user_a")
        assert first["token"] != second["token"]
        assert await db.get_share(first["token"]) is None
        assert await db.get_share(second["token"]) is not None

    async def test_get_share(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        result = await db.create_share_token("conv_1", "user_a")
        share = await db.get_share(result["token"])
        assert share is not None
        assert share["conversation_id"] == "conv_1"
        assert share["token"] == result["token"]

    async def test_get_share_nonexistent(self, test_db):
        assert await db.get_share("nonexistent_token") is None

    async def test_get_conversation_share(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        await db.create_share_token("conv_1", "user_a")
        share = await db.get_conversation_share("conv_1")
        assert share is not None
        assert share["token"]

    async def test_get_conversation_share_none(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        assert await db.get_conversation_share("conv_1") is None

    async def test_revoke_share(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        result = await db.create_share_token("conv_1", "user_a")
        assert await db.revoke_share("conv_1", "user_a") is True
        assert await db.get_share(result["token"]) is None

    async def test_revoke_share_wrong_user(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        await db.create_share_token("conv_1", "user_a")
        assert await db.revoke_share("conv_1", "user_b") is False

    async def test_revoke_nonexistent(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        assert await db.revoke_share("conv_1", "user_a") is False

    async def test_cascade_delete_removes_share(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        result = await db.create_share_token("conv_1", "user_a")
        await db.delete_conversation("conv_1", user_id="user_a")
        assert await db.get_share(result["token"]) is None

    async def test_get_shared_conversation(self, test_db):
        await db.create_conversation("conv_1", "Test", user_id="user_a")
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ])
        result = await db.create_share_token("conv_1", "user_a")
        conv = await db.get_shared_conversation(result["token"])
        assert conv is not None
        assert conv["id"] == "conv_1"
        assert len(conv["messages"]) == 2
        assert conv["messages"][0]["content"] == "Hello"

    async def test_get_shared_conversation_invalid_token(self, test_db):
        assert await db.get_shared_conversation("bad_token") is None
