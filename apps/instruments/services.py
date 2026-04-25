"""Domain services for instrument upserts with SCD2 semantics."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction

from .models import Instrument, Source

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InstrumentVersion:
    """Snapshot of an instrument as observed from upstream."""

    source_code: str
    external_id: str
    symbol: str
    name: str
    asset_class: str
    quote_currency: str
    metadata: dict
    observed_at: datetime


def upsert_instrument_scd2(version: InstrumentVersion) -> Instrument:
    """SCD2 upsert.

    Behavior:
    - If no current row exists for (source, external_id) → INSERT a new current row.
    - If a current row exists and the *tracked* attributes match → no-op, return it.
    - If a current row exists and attributes differ → close it (set valid_to,
      is_current=False), then INSERT a new current row.

    Tracked attributes for change detection: symbol, name, asset_class,
    quote_currency. Metadata changes are not considered material — they update
    the current row in place (could be promoted to SCD2 if needed).

    All steps in a single transaction. Returns the now-current row.
    """
    tracked_fields = ("symbol", "name", "asset_class", "quote_currency")

    with transaction.atomic():
        source = Source.objects.select_for_update().get(code=version.source_code)
        current = (
            Instrument.objects.select_for_update()
            .filter(source=source, external_id=version.external_id, is_current=True)
            .first()
        )

        new_payload = {
            "symbol": version.symbol,
            "name": version.name,
            "asset_class": version.asset_class,
            "quote_currency": version.quote_currency,
        }

        if current is None:
            instrument = Instrument.objects.create(
                source=source,
                external_id=version.external_id,
                metadata=version.metadata,
                valid_from=version.observed_at,
                is_current=True,
                **new_payload,
            )
            logger.info(
                "instrument_inserted",
                extra={"source": source.code, "external_id": version.external_id},
            )
            return instrument

        # Compare tracked fields
        material_change = any(
            getattr(current, f) != new_payload[f] for f in tracked_fields
        )

        if not material_change:
            # Soft-update of metadata
            if current.metadata != version.metadata:
                current.metadata = version.metadata
                current.save(update_fields=["metadata", "updated_at"])
            return current

        # Close previous version
        current.valid_to = version.observed_at
        current.is_current = False
        current.save(update_fields=["valid_to", "is_current", "updated_at"])

        # Open new current version
        new_instrument = Instrument.objects.create(
            source=source,
            external_id=version.external_id,
            metadata=version.metadata,
            valid_from=version.observed_at,
            is_current=True,
            **new_payload,
        )
        logger.info(
            "instrument_versioned",
            extra={
                "source": source.code,
                "external_id": version.external_id,
                "previous_id": current.pk,
                "new_id": new_instrument.pk,
            },
        )
        return new_instrument


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)
