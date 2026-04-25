from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("instruments", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="PriceCandle",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("resolution", models.CharField(
                    max_length=8,
                    choices=[
                        ("1m", "1 minute"), ("5m", "5 minutes"), ("15m", "15 minutes"),
                        ("1h", "1 hour"), ("4h", "4 hours"), ("1d", "1 day"),
                    ],
                )),
                ("ts", models.DateTimeField(help_text="Candle open time, UTC")),
                ("open", models.DecimalField(max_digits=24, decimal_places=12)),
                ("high", models.DecimalField(max_digits=24, decimal_places=12)),
                ("low", models.DecimalField(max_digits=24, decimal_places=12)),
                ("close", models.DecimalField(max_digits=24, decimal_places=12)),
                ("volume", models.DecimalField(max_digits=32, decimal_places=12, default=0)),
                ("ingested_at", models.DateTimeField(auto_now_add=True)),
                ("run_id", models.CharField(max_length=64, blank=True)),
                ("instrument", models.ForeignKey(
                    to="instruments.instrument",
                    on_delete=models.deletion.PROTECT,
                    related_name="candles",
                    db_index=False,
                )),
                ("source", models.ForeignKey(
                    to="instruments.source",
                    on_delete=models.deletion.PROTECT,
                    db_index=False,
                )),
            ],
            options={"db_table": "fact_price_candle"},
        ),
        migrations.AddIndex(
            model_name="pricecandle",
            index=models.Index(fields=["instrument", "-ts"], name="ix_price_inst_ts_desc"),
        ),
        migrations.AddIndex(
            model_name="pricecandle",
            index=models.Index(fields=["resolution", "ts"], name="ix_price_resolution_ts"),
        ),
        migrations.CreateModel(
            name="PriceSpot",
            fields=[
                ("instrument", models.OneToOneField(
                    primary_key=True, serialize=False,
                    to="instruments.instrument",
                    on_delete=models.deletion.CASCADE,
                    related_name="spot",
                )),
                ("price", models.DecimalField(max_digits=24, decimal_places=12)),
                ("change_24h_pct", models.DecimalField(
                    max_digits=10, decimal_places=4, null=True, blank=True,
                )),
                ("volume_24h", models.DecimalField(max_digits=32, decimal_places=12, default=0)),
                ("ts", models.DateTimeField()),
                ("source", models.ForeignKey(
                    to="instruments.source",
                    on_delete=models.deletion.PROTECT,
                )),
            ],
            options={"db_table": "fact_price_spot"},
        ),
        migrations.AddIndex(
            model_name="pricespot",
            index=models.Index(fields=["-ts"], name="ix_spot_ts_desc"),
        ),
    ]
