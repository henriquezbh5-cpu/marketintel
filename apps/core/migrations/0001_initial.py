"""DLQ table for terminally failed Celery tasks."""
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DeadLetterTask",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("task_id", models.CharField(max_length=64, unique=True)),
                ("task_name", models.CharField(max_length=255, db_index=True)),
                ("queue", models.CharField(max_length=64, blank=True, db_index=True)),
                ("args", models.JSONField(default=list)),
                ("kwargs", models.JSONField(default=dict)),
                ("exception", models.TextField()),
                ("traceback", models.TextField(blank=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("requeued_at", models.DateTimeField(null=True, blank=True)),
                ("resolved_at", models.DateTimeField(null=True, blank=True)),
            ],
            options={"db_table": "core_dead_letter_task", "ordering": ["-created_at"]},
        ),
    ]
