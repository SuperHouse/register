from django.db import migrations


def backfill_initial_stock_history(apps, schema_editor):
    """Seed one PartStockHistory row for every Part that has a known manually-tracked
    stock level but no history at all yet - every part that already existed before this
    history table was added (see Part.save() in models.py) - so the Stock History chart
    had nothing to show for a part despite a valid current stock figure.
    """
    Part = apps.get_model('erp', 'Part')
    PartStockHistory = apps.get_model('erp', 'PartStockHistory')

    parts = Part.objects.filter(stock__isnull=False, stock_history__isnull=True)
    PartStockHistory.objects.bulk_create([
        PartStockHistory(part=part, stock=part.stock) for part in parts
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0048_partstockhistory'),
    ]

    operations = [
        migrations.RunPython(backfill_initial_stock_history, migrations.RunPython.noop),
    ]
