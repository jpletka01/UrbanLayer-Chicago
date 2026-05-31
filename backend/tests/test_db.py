"""Tests for the SQLite persistence layer."""

import pytest
import pytest_asyncio

from backend import db


@pytest_asyncio.fixture
async def test_db(tmp_path):
    """Initialize an in-memory-like SQLite DB for testing."""
    from unittest.mock import patch, MagicMock

    mock_settings = MagicMock()
    mock_settings.db_path = str(tmp_path / "test.db")

    with patch("backend.db.get_settings", return_value=mock_settings):
        await db.init_db()
        yield
        await db.close_db()


@pytest.mark.asyncio
class TestConversations:
    async def test_create_and_list(self, test_db):
        await db.create_conversation("conv_1", "Test conversation")
        convos = await db.list_conversations()
        assert len(convos) == 1
        assert convos[0]["id"] == "conv_1"
        assert convos[0]["title"] == "Test conversation"
        assert convos[0]["message_count"] == 0

    async def test_get_conversation(self, test_db):
        await db.create_conversation("conv_1", "Test")
        conv = await db.get_conversation("conv_1")
        assert conv is not None
        assert conv["id"] == "conv_1"
        assert conv["messages"] == []

    async def test_get_nonexistent(self, test_db):
        assert await db.get_conversation("nope") is None

    async def test_delete_conversation(self, test_db):
        await db.create_conversation("conv_1", "Test")
        assert await db.delete_conversation("conv_1") is True
        assert await db.get_conversation("conv_1") is None

    async def test_delete_nonexistent(self, test_db):
        assert await db.delete_conversation("nope") is False

    async def test_clear_all(self, test_db):
        await db.create_conversation("conv_1", "A")
        await db.create_conversation("conv_2", "B")
        await db.clear_all_conversations()
        assert await db.list_conversations() == []

    async def test_list_ordered_by_updated(self, test_db):
        await db.create_conversation("conv_old", "Old")
        await db.create_conversation("conv_new", "New")
        convos = await db.list_conversations()
        assert convos[0]["id"] == "conv_new"


@pytest.mark.asyncio
class TestMessages:
    async def test_save_and_retrieve(self, test_db):
        await db.create_conversation("conv_1", "Test")
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ])
        conv = await db.get_conversation("conv_1")
        assert len(conv["messages"]) == 2
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][0]["content"] == "Hello"
        assert conv["messages"][1]["role"] == "assistant"

    async def test_count_user_messages(self, test_db):
        await db.create_conversation("conv_1", "Test")
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ])
        assert await db.count_user_messages("conv_1") == 2

    async def test_context_persisted(self, test_db):
        await db.create_conversation("conv_1", "Test")
        ctx = {"community_area": 24, "community_area_name": "West Town"}
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A", "context": ctx},
        ])
        conv = await db.get_conversation("conv_1")
        assert conv["messages"][1]["context"]["community_area"] == 24

    async def test_plan_persisted(self, test_db):
        await db.create_conversation("conv_1", "Test")
        plan = {"sources": ["crime_api"], "intent": "neighborhood_overview"}
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A", "plan": plan},
        ])
        conv = await db.get_conversation("conv_1")
        assert conv["messages"][1]["plan"]["sources"] == ["crime_api"]

    async def test_map_data_persisted(self, test_db):
        await db.create_conversation("conv_1", "Test")
        map_data = {"crimes": [{"lat": 41.9, "lon": -87.7}]}
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A", "map_data": map_data, "map_fetched_at": 1000},
        ])
        conv = await db.get_conversation("conv_1")
        assert conv["messages"][1]["map_data"]["crimes"][0]["lat"] == 41.9
        assert conv["messages"][1]["map_fetched_at"] == 1000

    async def test_update_map_data(self, test_db):
        await db.create_conversation("conv_1", "Test")
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A"},
        ])
        new_map = {"crimes": [{"lat": 42.0}]}
        await db.update_message_map_data("conv_1", 1, new_map, 2000)
        conv = await db.get_conversation("conv_1")
        assert conv["messages"][1]["map_data"]["crimes"][0]["lat"] == 42.0
        assert conv["messages"][1]["map_fetched_at"] == 2000

    async def test_cascade_delete(self, test_db):
        await db.create_conversation("conv_1", "Test")
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A"},
        ])
        await db.delete_conversation("conv_1")
        assert await db.count_user_messages("conv_1") == 0

    async def test_message_count_in_list(self, test_db):
        await db.create_conversation("conv_1", "Test")
        await db.save_messages("conv_1", [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ])
        convos = await db.list_conversations()
        assert convos[0]["message_count"] == 2

    async def test_title_updates_on_first_save(self, test_db):
        await db.create_conversation("conv_1", "New conversation")
        await db.save_messages("conv_1", [
            {"role": "user", "content": "What is the crime rate in Wicker Park?"},
            {"role": "assistant", "content": "A"},
        ])
        convos = await db.list_conversations()
        assert convos[0]["title"] == "What is the crime rate in Wicker Park?"


@pytest.mark.asyncio
class TestImport:
    async def test_import_conversations(self, test_db):
        convos = [
            {
                "id": "conv_old",
                "title": "Old chat",
                "messages": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello"},
                ],
                "createdAt": 1000,
                "updatedAt": 2000,
            },
        ]
        count = await db.import_conversations(convos)
        assert count == 1
        conv = await db.get_conversation("conv_old")
        assert len(conv["messages"]) == 2

    async def test_import_skips_duplicates(self, test_db):
        convos = [{"id": "conv_1", "title": "A", "messages": [], "createdAt": 1, "updatedAt": 1}]
        await db.import_conversations(convos)
        count = await db.import_conversations(convos)
        assert count == 0
