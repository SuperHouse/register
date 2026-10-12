from django.urls import reverse
import pytest

from crm.models import Org
from device.models import Design


@pytest.mark.django_db
def test_design_add_requires_staff(client, django_user_model):
    user = django_user_model.objects.create_user(email='user@example.com', password='pass')
    client.force_login(user)

    response = client.get(reverse('design_add'))
    assert response.status_code == 302
    assert Design.objects.count() == 0


@pytest.mark.django_db
def test_design_add_get_renders_form(client, django_user_model):
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    response = client.get(reverse('design_add'))
    assert response.status_code == 200
    assert 'form' in response.context


@pytest.mark.django_db
def test_design_add_creates_design_and_redirects_to_detail(client, django_user_model):
    org = Org.objects.create(company_name='Add Test Org')
    staff = django_user_model.objects.create_user(email='staff2@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    response = client.post(reverse('design_add'), {
        'client': org.pk,
        'name': 'New Design',
        'hw_version': '1.0',
        'sku': 'NEWSKU',
        'description': '',
        'price': '',
        'pcb_stock': '',
        'assembly_time_minutes': '0',
        'additional_materials': '0',
        'pcb_cost': '0',
        'packaging': '0',
    })

    design = Design.objects.get(sku='NEWSKU')
    assert design.name == 'New Design'
    assert design.hw_version == '1.0'
    assert design.client_id == org.pk
    assert response.status_code == 302
    assert response['Location'] == reverse('design_detail', args=[design.pk])


@pytest.mark.django_db
def test_design_add_rejects_duplicate_sku_and_hw_version(client, django_user_model):
    org = Org.objects.create(company_name='Dup Test Org')
    Design.objects.create(client=org, sku='DUP', name='Existing', hw_version='1.0')

    staff = django_user_model.objects.create_user(email='staff3@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    response = client.post(reverse('design_add'), {
        'client': org.pk,
        'name': 'Another',
        'hw_version': '1.0',
        'sku': 'DUP',
        'description': '',
        'price': '',
        'pcb_stock': '',
        'assembly_time_minutes': '0',
        'additional_materials': '0',
        'pcb_cost': '0',
        'packaging': '0',
    })

    assert response.status_code == 200
    assert Design.objects.filter(sku='DUP').count() == 1
    assert response.context['form'].errors
