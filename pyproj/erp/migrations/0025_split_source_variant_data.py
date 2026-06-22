from django.db import migrations


def split_sources_into_variants(apps, schema_editor):
    PartSource = apps.get_model('erp', 'PartSource')
    PartSourceVariant = apps.get_model('erp', 'PartSourceVariant')
    PartPriceBreak = apps.get_model('erp', 'PartPriceBreak')

    for source in PartSource.objects.all():
        variant = PartSourceVariant.objects.create(
            source=source,
            supplier_sku=source.supplier_sku,
            packaging=source.packaging,
            url=source.url,
        )
        PartPriceBreak.objects.filter(source=source).update(variant=variant)


def merge_variants_into_sources(apps, schema_editor):
    PartSource = apps.get_model('erp', 'PartSource')
    PartSourceVariant = apps.get_model('erp', 'PartSourceVariant')

    for variant in PartSourceVariant.objects.select_related('source'):
        source = variant.source
        source.supplier_sku = variant.supplier_sku
        source.packaging = variant.packaging
        source.url = variant.url
        source.save(update_fields=['supplier_sku', 'packaging', 'url'])


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0024_partsourcevariant'),
    ]

    operations = [
        migrations.RunPython(split_sources_into_variants, merge_variants_into_sources),
    ]
