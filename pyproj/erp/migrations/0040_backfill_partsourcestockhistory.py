from django.db import migrations


def backfill_initial_stock_history(apps, schema_editor):
    """Seed one PartSourceStockHistory row for every PartSource that has a known stock
    level but no history at all yet - mainly listings whose stock hasn't changed since
    before this history table was added (see PartSource.save() in models.py), so the
    Stock History chart/sparkline had nothing to show despite a valid current stock figure.
    """
    PartSource = apps.get_model('erp', 'PartSource')
    PartSourceStockHistory = apps.get_model('erp', 'PartSourceStockHistory')

    sources = PartSource.objects.filter(stock__isnull=False, stock_history__isnull=True)
    PartSourceStockHistory.objects.bulk_create([
        PartSourceStockHistory(source=source, stock=source.stock) for source in sources
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0039_bomsupplementrule'),
    ]

    operations = [
        migrations.RunPython(backfill_initial_stock_history, migrations.RunPython.noop),
    ]
