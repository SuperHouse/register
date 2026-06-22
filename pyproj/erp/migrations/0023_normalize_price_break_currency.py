from django.db import migrations


def normalize_currency_symbols(apps, schema_editor):
    PartPriceBreak = apps.get_model('erp', 'PartPriceBreak')
    PartPriceBreak.objects.filter(currency='$').update(currency='USD')


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0022_part_price_break'),
    ]

    operations = [
        migrations.RunPython(normalize_currency_symbols, migrations.RunPython.noop),
    ]
