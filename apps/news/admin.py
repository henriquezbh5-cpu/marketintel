from django.contrib import admin

from .models import NewsArticle


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "sentiment", "published_at")
    list_filter = ("source", "sentiment")
    search_fields = ("title", "summary", "external_id")
    date_hierarchy = "published_at"
    raw_id_fields = ("instruments",)
    readonly_fields = ("created_at", "updated_at", "fetched_at", "search")
