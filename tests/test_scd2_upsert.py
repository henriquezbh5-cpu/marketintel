"""SCD2 upsert behavior — most error-prone bit of the data model."""
from __future__ import annotations

from datetime import timedelta

import pytest

from apps.instruments.models import Instrument
from apps.instruments.services import InstrumentVersion, upsert_instrument_scd2


@pytest.mark.integration
def test_first_observation_creates_current_row(coingecko_source, utc_now):
    inst = upsert_instrument_scd2(
        InstrumentVersion(
            source_code="coingecko",
            external_id="bitcoin",
            symbol="BTC",
            name="Bitcoin",
            asset_class="crypto",
            quote_currency="USD",
            metadata={},
            observed_at=utc_now,
        )
    )
    assert inst.is_current is True
    assert inst.valid_to is None
    assert Instrument.objects.count() == 1


@pytest.mark.integration
def test_no_change_is_noop(coingecko_source, utc_now):
    payload = InstrumentVersion(
        source_code="coingecko",
        external_id="bitcoin",
        symbol="BTC",
        name="Bitcoin",
        asset_class="crypto",
        quote_currency="USD",
        metadata={},
        observed_at=utc_now,
    )
    upsert_instrument_scd2(payload)
    upsert_instrument_scd2(payload)

    assert Instrument.objects.count() == 1


@pytest.mark.integration
def test_material_change_versions_the_row(coingecko_source, utc_now):
    upsert_instrument_scd2(
        InstrumentVersion(
            source_code="coingecko",
            external_id="bitcoin",
            symbol="BTC",
            name="Bitcoin",
            asset_class="crypto",
            quote_currency="USD",
            metadata={},
            observed_at=utc_now,
        )
    )
    upsert_instrument_scd2(
        InstrumentVersion(
            source_code="coingecko",
            external_id="bitcoin",
            symbol="XBT",  # Symbol changed → material
            name="Bitcoin",
            asset_class="crypto",
            quote_currency="USD",
            metadata={},
            observed_at=utc_now + timedelta(minutes=1),
        )
    )

    rows = Instrument.objects.order_by("valid_from")
    assert rows.count() == 2
    assert rows[0].is_current is False
    assert rows[0].valid_to is not None
    assert rows[1].is_current is True
    assert rows[1].symbol == "XBT"


@pytest.mark.integration
def test_metadata_change_only_updates_in_place(coingecko_source, utc_now):
    upsert_instrument_scd2(
        InstrumentVersion(
            source_code="coingecko", external_id="bitcoin",
            symbol="BTC", name="Bitcoin",
            asset_class="crypto", quote_currency="USD",
            metadata={"market_cap_rank": 1},
            observed_at=utc_now,
        )
    )
    upsert_instrument_scd2(
        InstrumentVersion(
            source_code="coingecko", external_id="bitcoin",
            symbol="BTC", name="Bitcoin",
            asset_class="crypto", quote_currency="USD",
            metadata={"market_cap_rank": 1, "extra": "x"},
            observed_at=utc_now,
        )
    )
    assert Instrument.objects.count() == 1
    assert Instrument.objects.first().metadata == {"market_cap_rank": 1, "extra": "x"}
