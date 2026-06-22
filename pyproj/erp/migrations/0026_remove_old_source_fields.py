import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0025_split_source_variant_data'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='partpricebreak',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='partpricebreak',
            name='source',
        ),
        migrations.AlterField(
            model_name='partpricebreak',
            name='variant',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name='price_breaks', to='erp.partsourcevariant',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='partpricebreak',
            unique_together={('variant', 'quantity')},
        ),
        migrations.RemoveField(
            model_name='partsource',
            name='supplier_sku',
        ),
        migrations.RemoveField(
            model_name='partsource',
            name='packaging',
        ),
        migrations.RemoveField(
            model_name='partsource',
            name='url',
        ),
    ]
