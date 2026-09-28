from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app


def _status(**settings):
    s = MagicMock(stripe_secret_key="", stripe_price_id_report="", stripe_price_id_pro_monthly="")
    for k, v in settings.items():
        setattr(s, k, v)
    with patch("backend.main.get_settings", return_value=s):
        return TestClient(app).get("/api/payments/status").json()


def test_nothing_configured():
    assert _status() == {"reports": False, "subscriptions": False}


def test_each_purchase_needs_the_key_and_its_price():
    assert _status(stripe_secret_key="sk", stripe_price_id_report="price_r") == {
        "reports": True, "subscriptions": False,
    }
    assert _status(stripe_price_id_report="price_r") == {"reports": False, "subscriptions": False}
    assert _status(stripe_secret_key="sk", stripe_price_id_pro_monthly="price_p") == {
        "reports": False, "subscriptions": True,
    }
