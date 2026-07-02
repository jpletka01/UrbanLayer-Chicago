"""Tests for PTAXSIM-based property tax estimation."""

import asyncio

import aiosqlite
import pytest
from unittest.mock import patch

from backend.retrieval.property.tax_estimate import estimate_tax, close


SCHEMA = """
CREATE TABLE pin (
    year int NOT NULL,
    pin varchar(14) NOT NULL,
    class varchar(3) NOT NULL,
    tax_code_num varchar(5) NOT NULL,
    tax_bill_total double NOT NULL,
    av_mailed int NOT NULL,
    av_certified int NOT NULL,
    av_board int NOT NULL,
    av_clerk int NOT NULL,
    exe_homeowner int NOT NULL,
    exe_senior int NOT NULL,
    exe_freeze int NOT NULL,
    exe_longtime_homeowner int NOT NULL,
    exe_disabled int NOT NULL,
    exe_vet_returning int NOT NULL,
    exe_vet_dis_lt50 int NOT NULL,
    exe_vet_dis_50_69 int NOT NULL,
    exe_vet_dis_ge70 int NOT NULL,
    exe_vet_dis_100 int NOT NULL,
    exe_wwii int NOT NULL,
    exe_abate int NOT NULL,
    PRIMARY KEY (year, pin)
);

CREATE TABLE tax_code (
    year int NOT NULL,
    agency_num varchar(9) NOT NULL,
    agency_rate double NOT NULL,
    tax_code_num varchar(5) NOT NULL,
    tax_code_rate double NOT NULL,
    PRIMARY KEY (year, agency_num, tax_code_num)
);

CREATE TABLE agency_info (
    agency_num varchar(9) NOT NULL,
    agency_name varchar NOT NULL,
    agency_name_short varchar NOT NULL,
    agency_name_original varchar NOT NULL,
    major_type varchar(21) NOT NULL,
    minor_type varchar(10) NOT NULL,
    PRIMARY KEY (agency_num)
);
"""


@pytest.fixture
async def ptaxsim_db(tmp_path):
    """Create a minimal PTAXSIM test database."""
    await close()
    db_path = tmp_path / "ptaxsim_test.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.executescript(SCHEMA)

        await conn.execute(
            "INSERT INTO pin VALUES (2023, '17161000190000', '2-11', '77108', 10738.79, "
            "50723, 50723, 50723, 50723, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)"
        )
        await conn.execute(
            "INSERT INTO pin VALUES (2023, '17161000200000', '2-11', '77108', 14104.61, "
            "66621, 66621, 66621, 66621, 10000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)"
        )

        await conn.execute(
            "INSERT INTO agency_info VALUES ('010010000', 'COUNTY OF COOK', 'COOK', 'COOK', 'COUNTY', 'COUNTY')"
        )
        await conn.execute(
            "INSERT INTO agency_info VALUES ('030310000', 'BOARD OF EDUCATION', 'CPS', 'CPS', 'SCHOOL', 'SCHOOL')"
        )

        await conn.execute(
            "INSERT INTO tax_code VALUES (2023, '010010000', 0.386, '77108', 7.019)"
        )
        await conn.execute(
            "INSERT INTO tax_code VALUES (2023, '030310000', 3.829, '77108', 7.019)"
        )

        await conn.commit()

    yield db_path
    await close()


@pytest.mark.asyncio
async def test_estimate_tax_returns_breakdown(ptaxsim_db):
    with patch("backend.retrieval.property.tax_estimate.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = ptaxsim_db

        result = await estimate_tax(2023, "17161000190000")

        assert result is not None
        assert result["year"] == 2023
        assert result["pin"] == "17161000190000"
        assert result["tax_code"] == "77108"
        assert result["tax_bill_total"] == 10738.79
        assert result["assessed_value"] == 50723
        assert result["total_exemptions"] == 0
        assert len(result["line_items"]) == 2
        assert result["line_items"][0]["agency"] == "BOARD OF EDUCATION"
        assert result["line_items"][0]["rate"] == 3.829
        cps_amount = 10738.79 * (3.829 / 7.019)
        assert abs(result["line_items"][0]["amount"] - round(cps_amount, 2)) < 0.01


@pytest.mark.asyncio
async def test_estimate_tax_returns_none_for_missing_pin(ptaxsim_db):
    with patch("backend.retrieval.property.tax_estimate.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = ptaxsim_db

        result = await estimate_tax(2023, "99999999999999")
        assert result is None


@pytest.mark.asyncio
async def test_estimate_tax_handles_dashed_pin(ptaxsim_db):
    with patch("backend.retrieval.property.tax_estimate.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = ptaxsim_db

        result = await estimate_tax(2023, "17-16-100-019-0000")
        assert result is not None
        assert result["pin"] == "17161000190000"


@pytest.mark.asyncio
async def test_estimate_tax_with_exemptions(ptaxsim_db):
    with patch("backend.retrieval.property.tax_estimate.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = ptaxsim_db

        result = await estimate_tax(2023, "17161000200000")
        assert result is not None
        assert result["total_exemptions"] == 10000
        assert result["tax_bill_total"] == 14104.61
        # Itemized breakdown: only nonzero kinds, labeled, with EAV semantics
        assert result["exemptions"] == [
            {"kind": "Homeowner", "eav_reduction": 10000}
        ]


@pytest.mark.asyncio
async def test_estimate_tax_no_exemptions_empty_list(ptaxsim_db):
    with patch("backend.retrieval.property.tax_estimate.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = ptaxsim_db

        result = await estimate_tax(2023, "17161000190000")
        assert result is not None
        assert result["exemptions"] == []


@pytest.mark.asyncio
async def test_estimate_tax_disabled(ptaxsim_db):
    with patch("backend.retrieval.property.tax_estimate.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = False
        mock_settings.return_value.ptaxsim_db_path = ptaxsim_db

        result = await estimate_tax(2023, "17161000190000")
        assert result is None


@pytest.mark.asyncio
async def test_estimate_tax_missing_db(tmp_path):
    with patch("backend.retrieval.property.tax_estimate.get_settings") as mock_settings:
        mock_settings.return_value.ptaxsim_enabled = True
        mock_settings.return_value.ptaxsim_db_path = tmp_path / "nonexistent.db"

        result = await estimate_tax(2023, "17161000190000")
        assert result is None
