# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.urls import reverse
import pytest

from erp.models import Part, PartsOrder, PartsOrderLine


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.mark.django_db
def test_parts_order_list_renders(client, staff_user):
    PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')

    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_list'))

    assert response.status_code == 200
    assert 'SO1' in response.content.decode()


@pytest.mark.django_db
def test_parts_order_list_filters_by_q(client, staff_user):
    PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO-MATCH')
    PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO-OTHER')

    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_list'), {'q': 'MATCH'})
    content = response.content.decode()

    assert 'SO-MATCH' in content
    assert 'SO-OTHER' not in content


@pytest.mark.django_db
def test_parts_order_list_paginates(client, staff_user):
    for i in range(55):
        PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number=f'SO{i}')

    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_list'))

    assert response.context['page_obj'].paginator.num_pages == 2


@pytest.mark.django_db
def test_parts_order_detail_renders_line_items(client, staff_user):
    part = Part.objects.create(name='Test Part')
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(
        parts_order=parts_order, part=part, supplier_sku='SKU1', quantity=4, unit_price='1.50',
    )

    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_detail', args=[parts_order.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'SKU1' in content
    assert 'Test Part' in content


@pytest.mark.django_db
def test_parts_order_list_requires_staff(client, django_user_model):
    non_staff = django_user_model.objects.create_user(email='user@example.com', password='pass')
    client.force_login(non_staff)

    response = client.get(reverse('erp:parts_order_list'))

    assert response.status_code == 302


@pytest.mark.django_db
def test_parts_order_detail_requires_staff(client, django_user_model):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    non_staff = django_user_model.objects.create_user(email='user@example.com', password='pass')
    client.force_login(non_staff)

    response = client.get(reverse('erp:parts_order_detail', args=[parts_order.pk]))

    assert response.status_code == 302


@pytest.mark.django_db
def test_parts_order_refresh_requires_post(client, staff_user):
    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_refresh'))
    assert response.status_code == 405
