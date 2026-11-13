"""Check a provider's ID token and turn it into our identity claims (Phase 9, decision Item 121).

Checked: the signature against the provider's published keys (RS256 only, so ``alg: none`` and HS256-with-a-public-
key are refused), ``aud`` = our client id, the exact issuer, ``exp``/``iat`` (5 minutes of skew), and the ``nonce``
we put in the signed state. No userinfo call: the token is the only source.

Identity keys (email is never one):
  google      ``sub``
  microsoft   ``<tid>:<oid>`` (the issuer must be ``https://login.microsoftonline.com/<tid>/v2.0`` for the token's
              own ``tid``); its ``email`` is set by the tenant and is never treated as verified
  apple       ``sub``; ``email`` may be a private relay address
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Callable

import jwt
from jwt import PyJWKClient

from backend.identity.providers import PROVIDERS, client_id

LEEWAY_S = 300
_GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
_APPLE_ISSUER = "https://appleid.apple.com"
_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class TokenError(Exception):
    """The ID token failed a check. The message names the check, never the token."""


_jwks: dict[str, PyJWKClient] = {}

# Tests replace this to sign with their own key; production reads the provider's published keys (cached by PyJWT).
KeyResolver = Callable[[str, str], Any]


def _default_key(provider: str, token: str) -> Any:
    client = _jwks.get(provider)
    if client is None:
        client = _jwks[provider] = PyJWKClient(PROVIDERS[provider].jwks_url, cache_keys=True, lifespan=3600, timeout=10)
    return client.get_signing_key_from_jwt(token).key


key_resolver: KeyResolver = _default_key


def _truthy(v: Any) -> bool:
    return v is True or (isinstance(v, str) and v.lower() == "true")


async def verify_id_token(provider: str, token: str, nonce: str, *, apple_user: dict | None = None) -> dict:
    try:
        key = await asyncio.to_thread(key_resolver, provider, token)
    except Exception as exc:  # noqa: BLE001 - any key failure is a refused token
        raise TokenError("signing key") from exc
    try:
        c = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=client_id(provider),
            leeway=LEEWAY_S,
            options={"require": ["exp", "iat", "iss", "sub", "aud"], "verify_iss": False},
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError(type(exc).__name__) from exc
    if not nonce or c.get("nonce") != nonce:
        raise TokenError("nonce")

    if provider == "google":
        if c["iss"] not in _GOOGLE_ISSUERS:
            raise TokenError("issuer")
        return {
            "provider": "google",
            "subject": str(c["sub"]),
            "email": c.get("email"),
            "email_verified": _truthy(c.get("email_verified")),
            "private_email": False,
            "tenant": None,
            "name": c.get("name") or "",
            "picture_url": c.get("picture"),
        }
    if provider == "microsoft":
        tid = str(c.get("tid") or "")
        if not _GUID.match(tid) or c["iss"] != f"https://login.microsoftonline.com/{tid}/v2.0":
            raise TokenError("issuer")
        oid = str(c.get("oid") or c["sub"])
        return {
            "provider": "microsoft",
            "subject": f"{tid}:{oid}",
            "email": c.get("email"),
            "email_verified": False,
            "private_email": False,
            "tenant": tid,
            "name": c.get("name") or "",
            "picture_url": None,
        }
    if provider == "apple":
        if c["iss"] != _APPLE_ISSUER:
            raise TokenError("issuer")
        name = ""
        if apple_user:  # sent once, on the very first authorization, outside the token
            n = apple_user.get("name") or {}
            name = " ".join(x for x in (n.get("firstName"), n.get("lastName")) if isinstance(x, str) and x).strip()
        return {
            "provider": "apple",
            "subject": str(c["sub"]),
            "email": c.get("email"),
            "email_verified": _truthy(c.get("email_verified")),
            "private_email": _truthy(c.get("is_private_email")),
            "tenant": None,
            "name": name[:200],
            "picture_url": None,
        }
    raise TokenError("provider")
