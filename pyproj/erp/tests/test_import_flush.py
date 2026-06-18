import pytest

from device.management.commands.import_data import _flush_app_data
from erp.models import BomEquivalenceRule, BomExclusionRule, BomLibrarySetting


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
