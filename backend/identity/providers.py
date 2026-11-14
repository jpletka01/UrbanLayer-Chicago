"""The three sign-in providers (Phase 9, decision Item 121): Google, Apple, Microsoft. Never email.

A provider is offered when all of its settings are set. On a local review stack with ``AUTH_DEV_LOGIN`` on, a
provider without settings is offered as a stand-in ("Local test account") that runs the same callback code but
picks a fixed test person instead of asking the provider. Production refuses to start with that flag on
(``config.production_config_errors``), and the stand-in also needs a localhost front-end URL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import jwt

from backend.config import get_settings

ORDER = ("google", "apple", "microsoft")


@dataclass(frozen=True)
class Provider:
    name: str
    authorize_url: str
    token_url: str
    jwks_url: str
    scopes: str
    pkce: bool  # Apple doesn't offer PKCE: state + nonce + its signed ID token carry the flow
    form_post: bool  # Apple answers with a cross-site POST when name/email are asked for


PROVIDERS: dict[str, Provider] = {
    "google": Provider(
        "google",
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
        "https://www.googleapis.com/oauth2/v3/certs",
        "openid email profile",
        pkce=True,
        form_post=False,
    ),
    "microsoft": Provider(
        "microsoft",
        # `common`: work, school and personal Microsoft accounts. The issuer is per tenant, checked in tokens.py.
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "https://login.microsoftonline.com/common/discovery/v2.0/keys",
        "openid email profile",
        pkce=True,
        form_post=False,
    ),
    "apple": Provider(
        "apple",
        "https://appleid.apple.com/auth/authorize",
        "https://appleid.apple.com/auth/token",
        "https://appleid.apple.com/auth/keys",
        "name email",
        pkce=False,
        form_post=True,
    ),
}


def client_id(name: str) -> str:
    s = get_settings()
    return {"google": s.google_client_id, "microsoft": s.microsoft_client_id, "apple": s.apple_client_id}[name]


def _apple_key() -> str:
    s = get_settings()
    if s.apple_private_key:
        return s.apple_private_key.replace("\\n", "\n")
    if s.apple_private_key_path:
        try:
            return Path(s.apple_private_key_path).read_text()
        except OSError:
            return ""
    return ""


def configured(name: str) -> bool:
    s = get_settings()
    if name == "google":
        return bool(s.google_client_id and s.google_client_secret)
    if name == "microsoft":
        return bool(s.microsoft_client_id and s.microsoft_client_secret)
    if name == "apple":
        return bool(s.apple_client_id and s.apple_team_id and s.apple_key_id and (s.apple_private_key or s.apple_private_key_path))
    return False


def dev_login_allowed() -> bool:
    s = get_settings()
    if not s.auth_dev_login or s.environment == "production":
        return False
    host = urlparse(s.frontend_url).hostname or ""
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".localhost")


def stand_in(name: str) -> bool:
    """True when this provider runs as the local test stand-in."""
    return name in PROVIDERS and not configured(name) and dev_login_allowed()


def offered(name: str) -> bool:
    return name in PROVIDERS and (configured(name) or stand_in(name))


def available() -> list[dict]:
    return [{"id": n, "test": stand_in(n)} for n in ORDER if offered(n)]


def client_secret(name: str) -> str:
    s = get_settings()
    if name == "google":
        return s.google_client_secret
    if name == "microsoft":
        return s.microsoft_client_secret
    # Apple: a short-lived ES256 JWT signed with the owner's Sign in with Apple key, made per exchange.
    now = int(time.time())
    return jwt.encode(
        {"iss": s.apple_team_id, "iat": now, "exp": now + 300, "aud": "https://appleid.apple.com",
         "sub": s.apple_client_id},
        _apple_key(),
        algorithm="ES256",
        headers={"kid": s.apple_key_id},
    )


def callback_url(name: str) -> str:
    s = get_settings()
    base = (s.auth_callback_base or s.frontend_url).rstrip("/")
    return f"{base}/api/auth/{name}/callback"


# The stand-in's test people. Emails on example.com / Apple's relay domain only; subjects prefixed so they can
# never meet a real provider's. "a" shares one email across providers, which is the collision rule 2 must survive.
DEV_PEOPLE: dict[str, dict] = {
    "a": {"label": "Test person A", "email": "test-a@example.com", "name": "Test A"},
    "b": {"label": "Test person B", "email": "test-b@example.com", "name": "Test B"},
    "relay": {"label": "Test person A, email hidden (Apple relay)", "email": "test-a.relay@privaterelay.appleid.com",
              "name": "Test A", "private": True, "apple_only": True},
}


def dev_claims(provider: str, person: str) -> dict | None:
    p = DEV_PEOPLE.get(person)
    if p is None or (p.get("apple_only") and provider != "apple"):
        return None
    return {
        "provider": provider,
        "subject": f"dev-{person}",
        "email": p["email"],
        # Microsoft's email is never treated as verified (rule 5), the stand-in included.
        "email_verified": provider != "microsoft",
        "private_email": bool(p.get("private")),
        "tenant": "dev" if provider == "microsoft" else None,
        "name": p["name"],
        "picture_url": None,
    }
