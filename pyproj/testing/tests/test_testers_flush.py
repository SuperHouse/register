import pytest

from crm.models import Org
from device.management.commands.import_data import _flush_app_data
from device.models import Design
from testing.models import Tester, TestModule, TestModuleType


@pytest.mark.django_db
def test_flush_app_data_clears_testing_models():
    org = Org.objects.create(company_name='Flush Test Org')
    design = Design.objects.create(client=org, sku='FT1', name='Flush Test Design', hw_version='1.0')

    Tester.objects.create(name='Testomatic', version='2.3')
    module_type = TestModuleType.objects.create(name='MIC Tester', version='1.3')
    module_type.compatible_designs.add(design)
    TestModule.objects.create(module_type=module_type)

    assert Tester.objects.count() == 1
    assert TestModuleType.objects.count() == 1
    assert TestModule.objects.count() == 1

    _flush_app_data()

    assert Tester.objects.count() == 0
    assert TestModuleType.objects.count() == 0
    assert TestModule.objects.count() == 0
