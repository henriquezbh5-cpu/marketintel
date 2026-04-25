from django.contrib import admin

from .models import DeadLetterTask


@admin.register(DeadLetterTask)
class DeadLetterTaskAdmin(admin.ModelAdmin):
    list_display = ("task_name", "queue", "task_id", "attempts", "created_at", "resolved_at")
    list_filter = ("task_name", "queue", "resolved_at")
    search_fields = ("task_id", "task_name", "exception")
    readonly_fields = (
        "task_id", "task_name", "queue", "args", "kwargs", "exception",
        "traceback", "attempts", "created_at", "requeued_at",
    )
    actions = ["mark_resolved", "requeue_tasks"]

    @admin.action(description="Mark as resolved")
    def mark_resolved(self, _request, queryset):
        from django.utils import timezone
        queryset.update(resolved_at=timezone.now())

    @admin.action(description="Requeue tasks (idempotent)")
    def requeue_tasks(self, request, queryset):
        from celery import current_app
        from django.utils import timezone

        count = 0
        for dlq in queryset:
            current_app.send_task(
                dlq.task_name, args=dlq.args, kwargs=dlq.kwargs, queue=dlq.queue or "default",
            )
            count += 1
        queryset.update(requeued_at=timezone.now())
        self.message_user(request, f"Requeued {count} tasks.")
