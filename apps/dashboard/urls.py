from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("markets/", views.markets, name="markets"),
    path("markets/<str:symbol>/", views.symbol_detail, name="symbol"),
    path("news/", views.news, name="news"),
    path("system/", views.system, name="system"),

    # JSON endpoints for client-side polling
    path("_/kpis/",                  views.api_kpis,        name="api-kpis"),
    path("_/spots/",                 views.api_spots,       name="api-spots"),
    path("_/top-movers/",            views.api_top_movers,  name="api-top-movers"),
    path("_/candles/<str:symbol>/",  views.api_candles,     name="api-candles"),
    path("_/sparkline/<str:symbol>/", views.api_sparkline,  name="api-sparkline"),
    path("_/news/",                  views.api_news,        name="api-news"),
    path("_/system/",                views.api_system,      name="api-system"),
]
