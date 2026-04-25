"""factory_boy factories for fast test data creation."""
from __future__ import annotations

from datetime import datetime, timezone

import factory
from factory.django import DjangoModelFactory

from apps.api.models import APIKey
from apps.instruments.models import Instrument, Source
from apps.news.models import NewsArticle


class SourceFactory(DjangoModelFactory):
    class Meta:
        model = Source
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"src{n}")
    name = factory.Faker("company")
    base_url = factory.LazyAttribute(lambda o: f"https://{o.code}.example.com")
    is_active = True


class InstrumentFactory(DjangoModelFactory):
    class Meta:
        model = Instrument

    source = factory.SubFactory(SourceFactory)
    external_id = factory.Sequence(lambda n: f"asset-{n}")
    symbol = factory.Sequence(lambda n: f"SYM{n}")
    name = factory.Faker("company")
    asset_class = "crypto"
    quote_currency = "USD"
    metadata = {}
    valid_from = factory.LazyFunction(lambda: datetime(2020, 1, 1, tzinfo=timezone.utc))
    is_current = True


class NewsArticleFactory(DjangoModelFactory):
    class Meta:
        model = NewsArticle

    source = factory.SubFactory(SourceFactory)
    external_id = factory.Sequence(lambda n: f"art-{n}")
    title = factory.Faker("sentence")
    url = factory.Faker("url")
    summary = factory.Faker("paragraph")
    published_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    sentiment = "neutral"


class APIKeyFactory(DjangoModelFactory):
    class Meta:
        model = APIKey

    name = factory.Sequence(lambda n: f"key-{n}")
    key_hash = factory.Sequence(lambda n: f"hash{n:064d}")
    scope = APIKey.SCOPE_READ
    is_active = True
