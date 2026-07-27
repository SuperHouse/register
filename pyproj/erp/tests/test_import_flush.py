import pytest

from crm.models import Org
from device.management.commands.import_data import _flush_app_data
from device.models import Design
from erp.models import Batch, BomEquivalenceRule, BomExclusionRule, BomLibrarySetting, Part, PartsCartLine


@pytest.mark.django_db
def test_flush_app_data_clears_bom_filter_models():
    BomExclusionRule.objects.create(library='Test', device='TP')
    BomEquivalenceRule.objects.create(from_device='RES', to_device='LINK')
    BomLibrarySetting.objects.create(library='Test', ignore_value=True)

    assert BomExclusionRule.objects.count() == 1
    assert BomEquivalenceRule.objects.count() == 1
    assert BomLibrarySetting.objects.count() == 1

    _flush_app_data()

    assert BomExclusionRule.objects.count() == 0
    assert BomEquivalenceRule.objects.count() == 0
    assert BomLibrarySetting.objects.count() == 0


@pytest.mark.django_db
def test_flush_app_data_clears_parts_cart_lines():
    org = Org.objects.create(company_name='Flush Test Org')
    design = Design.objects.create(client=org, sku='FLT1', name='Flush Test Design', hw_version='1.0')
    batch = Batch.objects.create(design=design, quantity=10)
    part = Part.objects.create(name='Flush Test Part')

    PartsCartLine.objects.create(part=part, batch=batch, quantity=5)
    PartsCartLine.objects.create(part=part, quantity=2, notes='R&D')

    assert PartsCartLine.objects.count() == 2

    _flush_app_data()

    assert PartsCartLine.objects.count() == 0
    assert Batch.objects.count() == 0
    assert Part.objects.count() == 0
