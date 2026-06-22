from django.db import migrations


def merge_duplicate_listings(apps, schema_editor):
    """Collapse pre-existing listings that are really the same manufacturer SKU.

    Before this app split PartSource into a listing + variant model, suppliers like
    DigiKey that expose several packaging-specific SKUs (cut tape, tape & reel, etc.)
    for one physical part ended up as separate PartSource rows with duplicated
    manufacturer_sku/stock. The schema split preserved that 1:1, so this groups them
    by (part, supplier_name, manufacturer_sku) and merges each group's variants onto
    one canonical listing.
    """
    PartSource = apps.get_model('erp', 'PartSource')
    PartSourceVariant = apps.get_model('erp', 'PartSourceVariant')

    groups = {}
    for source in PartSource.objects.exclude(manufacturer_sku='').order_by('pk'):
        key = (source.part_id, source.supplier_name.lower(), source.manufacturer_sku.lower())
        groups.setdefault(key, []).append(source)

    for group in groups.values():
        if len(group) < 2:
            continue
        canonical = group[0]
        for duplicate in group[1:]:
            PartSourceVariant.objects.filter(source=duplicate).update(source=canonical)
            if canonical.stock is None and duplicate.stock is not None:
                canonical.stock = duplicate.stock
                canonical.save(update_fields=['stock'])
            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('erp', '0026_remove_old_source_fields'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_listings, migrations.RunPython.noop),
    ]
