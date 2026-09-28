"""Production refuses to start with settings that fail open."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.config import Settings, production_config_errors, validate_production

GOOD = dict(
    environment="production",
    google_client_id="client-id",
    google_client_secret="client-secret",
    jwt_secret="x" * 48,
    auth_cookie_secure=True,
    frontend_url="https://urbanlayerchicago.com",
    stripe_secret_key="sk_test_placeholder",
    stripe_webhook_secret="whsec_placeholder",
)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**GOOD, **overrides})


def test_complete_production_config_starts():
    assert production_config_errors(_settings()) == []
    validate_production(_settings())


@pytest.mark.parametrize(
    "override, message",
    [
        ({"google_client_id": ""}, "GOOGLE_CLIENT_ID"),
        ({"jwt_secret": ""}, "JWT_SECRET"),
        ({"jwt_secret": "short"}, "JWT_SECRET"),
        ({"jwt_secret": "dev-insecure-key-do-not-use-in-production"}, "JWT_SECRET"),
        ({"auth_cookie_secure": False}, "AUTH_COOKIE_SECURE"),
        ({"frontend_url": "http://urbanlayerchicago.com"}, "FRONTEND_URL"),
        ({"stripe_webhook_secret": ""}, "STRIPE_WEBHOOK_SECRET"),
    ],
)
def test_each_fail_open_setting_blocks_startup(override, message):
    with pytest.raises(RuntimeError, match=message):
        validate_production(_settings(**override))


def test_stripe_is_optional_when_payments_are_off():
    assert production_config_errors(_settings(stripe_secret_key="", stripe_webhook_secret="")) == []


def test_development_keeps_permissive_defaults():
    validate_production(Settings(_env_file=None, environment="development"))


async def test_unsigned_webhook_rejected_in_production():
    from fastapi import HTTPException

    from backend import payments

    settings = MagicMock(environment="production", stripe_webhook_secret="", stripe_secret_key="sk")
    request = MagicMock()

    async def _body():
        return b'{"type": "checkout.session.completed", "data": {"object": {}}}'

    request.body = _body
    request.headers = {}
    with patch("backend.payments.get_settings", return_value=settings), \
            patch("backend.payments._configure_stripe"):
        with pytest.raises(HTTPException) as exc_info:
            await payments.handle_webhook(request)
    assert exc_info.value.status_code == 503
