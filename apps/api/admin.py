from django.contrib import admin

from .models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "scope", "is_active", "created_at", "last_used_at")
    list_filter = ("scope", "is_active")
    search_fields = ("name", "user__username")
    readonly_fields = ("key_hash", "created_at", "last_used_at")
