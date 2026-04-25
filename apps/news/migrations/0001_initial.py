import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("instruments", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="NewsArticle",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("external_id", models.CharField(max_length=128)),
                ("title", models.TextField()),
                ("url", models.URLField(max_length=1024)),
                ("summary", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(db_index=True)),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
                ("sentiment", models.CharField(
                    max_length=16, default="neutral",
                    choices=[
                        ("positive", "Positive"),
                        ("neutral", "Neutral"),
                        ("negative", "Negative"),
                    ],
                )),
                ("sentiment_score", models.FloatField(null=True, blank=True)),
                ("metadata", models.JSONField(default=dict, blank=True)),
                ("search", django.contrib.postgres.search.SearchVectorField(null=True, editable=False)),
                ("source", models.ForeignKey(
                    to="instruments.source",
                    on_delete=models.deletion.PROTECT,
                    related_name="articles",
                )),
                ("instruments", models.ManyToManyField(
                    to="instruments.instrument", related_name="news", blank=True,
                )),
            ],
            options={"ordering": ["-published_at"]},
        ),
        migrations.AddConstraint(
            model_name="newsarticle",
            constraint=models.UniqueConstraint(
                fields=["source", "external_id"], name="uniq_news_source_extid",
            ),
        ),
        migrations.AddIndex(
            model_name="newsarticle",
            index=models.Index(fields=["-published_at"], name="ix_news_published_desc"),
        ),
        migrations.AddIndex(
            model_name="newsarticle",
            index=models.Index(
                fields=["sentiment", "-published_at"], name="ix_news_sent_pub",
            ),
        ),
        migrations.AddIndex(
            model_name="newsarticle",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search"], name="ix_news_search_gin",
            ),
        ),
    ]
