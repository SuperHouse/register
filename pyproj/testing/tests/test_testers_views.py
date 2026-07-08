import pytest
from django.urls import reverse

from crm.models import Org
from device.models import Design
from testing.models import Tester, TestModule, TestModuleType


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='tester-staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def plain_user(django_user_model):
    return django_user_model.objects.create_user(email='tester-plain@example.com', password='plainy')


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Tester View Org')
    return Design.objects.create(client=org, sku='TV1', name='Tester View Design', hw_version='1.0')


@pytest.fixture
def tester():
    return Tester.objects.create(name='Testomatic', version='2.3')


@pytest.fixture
def module_type():
    return TestModuleType.objects.create(name='MIC Tester', version='1.3')


@pytest.fixture
def module(module_type):
    return TestModule.objects.create(module_type=module_type)


@pytest.mark.django_db
def test_non_staff_users_are_redirected(client, plain_user, tester, module_type, module, design):
    urls = [
        reverse('testing:tester_list'),
        reverse('testing:tester_add'),
        reverse('testing:tester_edit', args=[tester.pk]),
        reverse('testing:tester_delete', args=[tester.pk]),
        reverse('testing:test_module_add'),
        reverse('testing:test_module_edit', args=[module.pk]),
        reverse('testing:test_module_delete', args=[module.pk]),
        reverse('testing:test_module_type_list'),
        reverse('testing:test_module_type_add'),
        reverse('testing:test_module_type_edit', args=[module_type.pk]),
        reverse('testing:test_module_type_delete', args=[module_type.pk]),
        reverse('testing:test_module_type_design_add', args=[module_type.pk]),
        reverse('testing:test_module_type_design_remove', args=[module_type.pk, design.pk]),
    ]
    client.force_login(plain_user)
    for url in urls:
        response = client.get(url)
        assert response.status_code == 302, url


@pytest.mark.django_db
def test_staff_sees_list_edit_and_delete_pages(client, staff_user, tester, module_type, module):
    client.force_login(staff_user)
    for url in [
        reverse('testing:tester_list'),
        reverse('testing:test_module_type_list'),
        reverse('testing:tester_edit', args=[tester.pk]),
        reverse('testing:tester_delete', args=[tester.pk]),
        reverse('testing:test_module_edit', args=[module.pk]),
        reverse('testing:test_module_delete', args=[module.pk]),
        reverse('testing:test_module_type_edit', args=[module_type.pk]),
        reverse('testing:test_module_type_delete', args=[module_type.pk]),
    ]:
        response = client.get(url)
        assert response.status_code == 200, url


@pytest.mark.django_db
def test_tester_list_shows_testers_and_modules(client, staff_user, tester, module):
    client.force_login(staff_user)
    content = client.get(reverse('testing:tester_list')).content.decode()
    assert 'Testomatic' in content
    assert 'MIC Tester' in content  # the module's type name, shown in the Test Modules card
    assert f'#{tester.pk}' in content
    assert f'#{module.pk}' in content


@pytest.mark.django_db
def test_module_type_list_shows_module_types(client, staff_user, module_type):
    client.force_login(staff_user)
    content = client.get(reverse('testing:test_module_type_list')).content.decode()
    assert 'MIC Tester' in content
    assert f'#{module_type.pk}' in content


@pytest.mark.django_db
def test_tester_inline_add(client, staff_user):
    client.force_login(staff_user)
    response = client.post(reverse('testing:tester_add'), {
        'tester-name': 'New Chassis',
        'tester-version': '1.0',
        'tester-notes': 'Bench 2',
    })
    assert response.status_code == 302
    tester = Tester.objects.get(name='New Chassis')
    assert tester.version == '1.0'
    assert tester.notes == 'Bench 2'


@pytest.mark.django_db
def test_tester_inline_add_invalid_creates_nothing(client, staff_user):
    client.force_login(staff_user)
    response = client.post(reverse('testing:tester_add'), {'tester-name': ''})
    assert response.status_code == 302
    assert Tester.objects.count() == 0


@pytest.mark.django_db
def test_test_module_inline_add(client, staff_user, module_type):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_module_add'), {
        'module-module_type': module_type.pk,
        'module-notes': 'Spare unit',
    })
    assert response.status_code == 302
    module = TestModule.objects.get(notes='Spare unit')
    assert module.module_type == module_type


@pytest.mark.django_db
def test_test_module_type_inline_add_redirects_to_edit_page(client, staff_user):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_module_type_add'), {
        'module_type-name': 'Relay Tester',
        'module_type-version': '1.0',
    })
    module_type = TestModuleType.objects.get(name='Relay Tester')
    assert response.status_code == 302
    assert response.url == reverse('testing:test_module_type_edit', args=[module_type.pk])


@pytest.mark.django_db
def test_tester_edit_updates(client, staff_user, tester):
    client.force_login(staff_user)
    response = client.post(reverse('testing:tester_edit', args=[tester.pk]), {
        'name': 'Renamed',
        'version': '2.4',
        'notes': '',
    })
    assert response.status_code == 302
    tester.refresh_from_db()
    assert tester.name == 'Renamed'
    assert tester.version == '2.4'


@pytest.mark.django_db
def test_tester_delete(client, staff_user, tester):
    client.force_login(staff_user)
    response = client.post(reverse('testing:tester_delete', args=[tester.pk]))
    assert response.status_code == 302
    assert Tester.objects.count() == 0


@pytest.mark.django_db
def test_module_type_delete_blocked_while_modules_exist(client, staff_user, module_type, module):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_module_type_delete', args=[module_type.pk]))
    assert response.status_code == 302
    assert TestModuleType.objects.filter(pk=module_type.pk).exists()

    module.delete()
    client.post(reverse('testing:test_module_type_delete', args=[module_type.pk]))
    assert not TestModuleType.objects.filter(pk=module_type.pk).exists()


@pytest.mark.django_db
def test_design_add_and_remove(client, staff_user, module_type, design):
    client.force_login(staff_user)

    response = client.post(
        reverse('testing:test_module_type_design_add', args=[module_type.pk]),
        {'design': design.pk},
    )
    assert response.status_code == 302
    assert list(module_type.compatible_designs.all()) == [design]

    # Already-added designs are excluded from the add dropdown.
    content = client.get(reverse('testing:test_module_type_edit', args=[module_type.pk])).content.decode()
    assert f'<option value="{design.pk}"' not in content

    response = client.post(
        reverse('testing:test_module_type_design_remove', args=[module_type.pk, design.pk]),
    )
    assert response.status_code == 302
    assert module_type.compatible_designs.count() == 0
    assert Design.objects.filter(pk=design.pk).exists()


@pytest.mark.django_db
def test_design_add_rejects_already_compatible_design(client, staff_user, module_type, design):
    module_type.compatible_designs.add(design)
    client.force_login(staff_user)
    response = client.post(
        reverse('testing:test_module_type_design_add', args=[module_type.pk]),
        {'design': design.pk},
    )
    assert response.status_code == 302
    assert module_type.compatible_designs.count() == 1
