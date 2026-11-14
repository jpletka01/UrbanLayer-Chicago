from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app


def _status(**settings):
    s = MagicMock(stripe_secret_key="", stripe_webhook_secret="", stripe_price_id_report="",
                  stripe_price_id_pro_monthly="", stripe_price_id_pro_yearly="")
    for k, v in settings.items():
        setattr(s, k, v)
    with patch("backend.payments.get_settings", return_value=s):
        return TestClient(app).get("/api/payments/status").json()


FULL = dict(stripe_secret_key="sk_test_x", stripe_webhook_secret="whsec_x",
            stripe_price_id_pro_monthly="price_m", stripe_price_id_pro_yearly="price_y")


def test_nothing_configured():
    assert _status() == {"reports": False, "subscriptions": False}


def test_purchases_need_every_setting():
    """Merged dark (Item 123): Pro is on only with the key, the webhook secret and both prices."""
    assert _status(**FULL) == {"reports": False, "subscriptions": True}
    for missing in FULL:
        assert _status(**{**FULL, missing: ""})["subscriptions"] is False


def test_report_purchase_is_retired():
    assert _status(**FULL, stripe_price_id_report="price_r")["reports"] is False
