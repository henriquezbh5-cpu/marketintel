from django.contrib import admin

from .models import Instrument, Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "source", "asset_class", "is_current", "valid_from")
    list_filter = ("source", "asset_class", "is_current")
    search_fields = ("symbol", "name", "external_id")
    date_hierarchy = "valid_from"
    readonly_fields = ("created_at", "updated_at")
