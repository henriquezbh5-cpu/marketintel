from rest_framework.routers import DefaultRouter

from .views import (
    InstrumentViewSet,
    NewsViewSet,
    PriceCandleViewSet,
    PriceSpotViewSet,
    SourceViewSet,
)

router = DefaultRouter()
router.register("sources", SourceViewSet, basename="source")
router.register("instruments", InstrumentViewSet, basename="instrument")
router.register("candles", PriceCandleViewSet, basename="candle")
router.register("spot", PriceSpotViewSet, basename="spot")
router.register("news", NewsViewSet, basename="news")

urlpatterns = router.urls
