from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=128)),
                ("base_url", models.URLField()),
                ("docs_url", models.URLField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="Instrument",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("valid_from", models.DateTimeField(db_index=True)),
                ("valid_to", models.DateTimeField(null=True, blank=True, db_index=True)),
                ("is_current", models.BooleanField(default=True)),
                ("external_id", models.CharField(max_length=128)),
                ("symbol", models.CharField(max_length=32, db_index=True)),
                ("name", models.CharField(max_length=256)),
                ("asset_class", models.CharField(
                    max_length=16,
                    default="crypto",
                    choices=[
                        ("crypto", "Cryptocurrency"),
                        ("equity", "Equity"),
                        ("fx", "Foreign exchange"),
                        ("commodity", "Commodity"),
                    ],
                )),
                ("quote_currency", models.CharField(max_length=16, default="USD")),
                ("metadata", models.JSONField(default=dict, blank=True)),
                ("source", models.ForeignKey(
                    to="instruments.source",
                    on_delete=models.deletion.PROTECT,
                    related_name="instruments",
                )),
            ],
            options={"ordering": ["symbol"]},
        ),
        migrations.AddConstraint(
            model_name="instrument",
            constraint=models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=Q(is_current=True),
                name="uniq_current_instrument_per_source",
            ),
        ),
        migrations.AddIndex(
            model_name="instrument",
            index=models.Index(fields=["symbol", "asset_class"], name="ix_inst_sym_asset"),
        ),
        migrations.AddIndex(
            model_name="instrument",
            index=models.Index(
                fields=["source", "external_id", "valid_from"],
                name="ix_inst_src_ext_validfrom",
            ),
        ),
    ]
