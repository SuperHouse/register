# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
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


@pytest.mark.django_db
def test_toggle_received_marks_line_received(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, quantity=1)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert response.status_code == 200
    assert response.json() == {'ok': True, 'received': True}
    line.refresh_from_db()
    assert line.received is True
    assert line.received_dt is not None


@pytest.mark.django_db
def test_toggle_received_unmarks_an_already_received_line(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, quantity=1, received=True)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert response.json() == {'ok': True, 'received': False}
    line.refresh_from_db()
    assert line.received is False
    assert line.received_dt is None


@pytest.mark.django_db
def test_toggle_received_adds_quantity_to_part_stock_from_null(client, staff_user):
    part = Part.objects.create(name='Widget')
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=5)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    part.refresh_from_db()
    assert part.stock == 5


@pytest.mark.django_db
def test_toggle_received_adds_quantity_to_existing_part_stock(client, staff_user):
    part = Part.objects.create(name='Widget', stock=10)
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=5)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    part.refresh_from_db()
    assert part.stock == 15


@pytest.mark.django_db
def test_toggle_received_unmarking_subtracts_quantity_and_allows_negative(client, staff_user):
    part = Part.objects.create(name='Widget', stock=3)
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=5, received=True)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert response.json() == {'ok': True, 'received': False}
    part.refresh_from_db()
    assert part.stock == -2


@pytest.mark.django_db
def test_toggle_received_with_no_matched_part_does_not_error(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, part=None, quantity=5)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert response.json() == {'ok': True, 'received': True}


@pytest.mark.django_db
def test_toggle_received_requires_post(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, quantity=1)

    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert response.status_code == 405


@pytest.mark.django_db
def test_receive_all_marks_every_unreceived_line(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(parts_order=parts_order, quantity=1)
    PartsOrderLine.objects.create(parts_order=parts_order, quantity=2)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))

    assert response.json() == {'ok': True, 'count': 2}
    assert parts_order.lines.filter(received=True).count() == 2


@pytest.mark.django_db
def test_receive_all_does_not_touch_already_received_lines(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    original_dt = timezone.now() - timedelta(days=1)
    already_received = PartsOrderLine.objects.create(
        parts_order=parts_order, quantity=1, received=True, received_dt=original_dt,
    )
    PartsOrderLine.objects.create(parts_order=parts_order, quantity=2)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))

    assert response.json() == {'ok': True, 'count': 1}
    already_received.refresh_from_db()
    assert already_received.received_dt == original_dt


@pytest.mark.django_db
def test_receive_all_adds_quantities_to_matched_parts_stock(client, staff_user):
    part_a = Part.objects.create(name='Widget A', stock=1)
    part_b = Part.objects.create(name='Widget B')
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(parts_order=parts_order, part=part_a, quantity=4)
    PartsOrderLine.objects.create(parts_order=parts_order, part=part_b, quantity=7)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))

    part_a.refresh_from_db()
    part_b.refresh_from_db()
    assert part_a.stock == 5
    assert part_b.stock == 7


@pytest.mark.django_db
def test_receive_all_aggregates_multiple_lines_for_the_same_part(client, staff_user):
    part = Part.objects.create(name='Widget', stock=2)
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=3, supplier_line_number='1')
    PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=4, supplier_line_number='2')

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))

    part.refresh_from_db()
    assert part.stock == 9


@pytest.mark.django_db
def test_receive_all_does_not_double_count_already_received_lines_stock(client, staff_user):
    part = Part.objects.create(name='Widget', stock=10)
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=5, received=True)
    PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=3, received=False)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))

    part.refresh_from_db()
    assert part.stock == 13


@pytest.mark.django_db
def test_receive_all_requires_post(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))
    assert response.status_code == 405
