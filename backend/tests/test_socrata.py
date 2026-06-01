import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from backend.retrieval.socrata import socrata_get, SocrataError


class TestSocrataGet:
    @pytest.mark.asyncio
    async def test_requires_limit_guard(self, mock_settings):
        with patch("backend.retrieval.socrata.get_settings", return_value=mock_settings):
            with pytest.raises(ValueError, match="missing \\$limit guard"):
                await socrata_get("test-dataset", {"$where": "foo='bar'"})

    @pytest.mark.asyncio
    async def test_successful_request(self, mock_settings):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("backend.retrieval.socrata.get_settings", return_value=mock_settings):
            result = await socrata_get(
                "test-dataset",
                {"$where": "foo='bar'", "$limit": 10},
                client=mock_client,
            )

        assert result == [{"id": 1}, {"id": 2}]
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "test-dataset.json" in call_args[0][0]
        assert call_args[1]["headers"]["X-App-Token"] == "test-token"

    @pytest.mark.asyncio
    async def test_retries_on_server_error(self, mock_settings):
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.request = MagicMock()

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = [{"ok": True}]
        success_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[error_response, success_response])
        mock_client.aclose = AsyncMock()

        with patch("backend.retrieval.socrata.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.socrata.asyncio.sleep", new_callable=AsyncMock):
                result = await socrata_get(
                    "test-dataset",
                    {"$limit": 10},
                    client=mock_client,
                )

        assert result == [{"ok": True}]
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_socrata_error_after_max_retries(self, mock_settings):
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.request = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=error_response)
        mock_client.aclose = AsyncMock()

        with patch("backend.retrieval.socrata.get_settings", return_value=mock_settings):
            with patch("backend.retrieval.socrata.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(SocrataError, match="Socrata request failed"):
                    await socrata_get(
                        "test-dataset",
                        {"$limit": 10},
                        client=mock_client,
                    )

        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_no_app_token_header_when_not_configured(self, mock_settings):
        mock_settings.socrata_app_token = ""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with patch("backend.retrieval.socrata.get_settings", return_value=mock_settings):
            await socrata_get(
                "test-dataset",
                {"$limit": 10},
                client=mock_client,
            )

        call_args = mock_client.get.call_args
        assert "X-App-Token" not in call_args[1]["headers"]


@pytest.mark.integration
class TestSocrataLive:
    """Hits the real Chicago Data Portal (free, no key required).

    The mocked tests above cover the wrapper's transport mechanics (retries,
    the $limit guard, header logic) which a live API can't reproduce; these
    verify we can actually reach Socrata and parse a real response.
    """

    @pytest.mark.asyncio
    async def test_crime_dataset_returns_rows(self):
        # ijzp-q8t2 is the Crimes dataset; uses real settings (socrata_base).
        rows = await socrata_get("ijzp-q8t2", {"$limit": 3, "$order": "date DESC"})
        assert isinstance(rows, list)
        assert len(rows) <= 3
        if rows:
            assert "primary_type" in rows[0]
