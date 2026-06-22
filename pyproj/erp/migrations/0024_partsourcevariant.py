import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0023_normalize_price_break_currency'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartSourceVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('supplier_sku', models.CharField(blank=True, max_length=200)),
                ('packaging', models.CharField(blank=True, max_length=100)),
                ('url', models.URLField(blank=True)),
                (
                    'source',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='variants', to='erp.partsource',
                    ),
                ),
            ],
            options={
                'ordering': ['supplier_sku'],
            },
        ),
        migrations.AddField(
            model_name='partpricebreak',
            name='variant',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='price_breaks',
                to='erp.partsourcevariant',
            ),
        ),
    ]
