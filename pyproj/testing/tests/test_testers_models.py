import pytest
from django.db.models import ProtectedError

from crm.models import Org
from device.models import Design
from testing.models import Tester, TestModule, TestModuleType


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Tester Test Org')
    return Design.objects.create(client=org, sku='TT1', name='Tester Test Design', hw_version='1.0')


@pytest.mark.django_db
def test_tester_str_with_and_without_version():
    assert str(Tester.objects.create(name='Testomatic', version='2.3')) == 'Testomatic v2.3'
    assert str(Tester.objects.create(name='Testomatic')) == 'Testomatic'


@pytest.mark.django_db
def test_module_type_str_with_and_without_version():
    assert str(TestModuleType.objects.create(name='MIC Tester', version='1.3')) == 'MIC Tester v1.3'
    assert str(TestModuleType.objects.create(name='MIC Tester')) == 'MIC Tester'


@pytest.mark.django_db
def test_module_str_shows_pk_and_type():
    module_type = TestModuleType.objects.create(name='MIC Tester', version='1.3')
    module = TestModule.objects.create(module_type=module_type)
    assert str(module) == f'#{module.pk} MIC Tester v1.3'


@pytest.mark.django_db
def test_testers_ordered_by_name():
    Tester.objects.create(name='Zeta')
    Tester.objects.create(name='Alpha')
    assert [t.name for t in Tester.objects.all()] == ['Alpha', 'Zeta']


@pytest.mark.django_db
def test_compatible_designs_add_and_remove(design):
    module_type = TestModuleType.objects.create(name='MIC Tester')
    module_type.compatible_designs.add(design)
    assert list(module_type.compatible_designs.all()) == [design]
    assert list(design.test_module_types.all()) == [module_type]

    module_type.compatible_designs.remove(design)
    assert module_type.compatible_designs.count() == 0
    assert Design.objects.filter(pk=design.pk).exists()


@pytest.mark.django_db
def test_module_type_delete_protected_while_modules_exist():
    module_type = TestModuleType.objects.create(name='MIC Tester')
    module = TestModule.objects.create(module_type=module_type)

    with pytest.raises(ProtectedError):
        module_type.delete()

    module.delete()
    module_type.delete()
    assert TestModuleType.objects.count() == 0
