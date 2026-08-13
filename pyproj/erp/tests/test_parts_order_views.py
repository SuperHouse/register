# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from crm.models import Org
from device.models import Design
from erp.models import Part, PartsOrder, PartsOrderLine


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Parts Order View Test Org')
    return Design.objects.create(client=org, sku='POV1', name='Parts Order View Test Design', hw_version='1.0')


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
def test_toggle_received_logs_part_stock_history(client, staff_user):
    # _apply_part_stock_deltas() used to write via a bare queryset .update(), which bypasses
    # Part.save() and would silently skip logging a PartStockHistory snapshot (issue #99).
    part = Part.objects.create(name='Widget', stock=10)
    part.stock_history.all().delete()
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=5)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert list(part.stock_history.order_by('recorded_dt').values_list('stock', flat=True)) == [15]


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


# --- design-linked receiving (issue #100 - JLCPCB lines credit Design.pcb_stock, not Part.stock) ---

@pytest.mark.django_db
def test_toggle_received_adds_quantity_to_design_pcb_stock_from_null(client, staff_user, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=5)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    design.refresh_from_db()
    assert design.pcb_stock == 5


@pytest.mark.django_db
def test_toggle_received_adds_quantity_to_existing_design_pcb_stock(client, staff_user, design):
    design.pcb_stock = 10
    design.save(update_fields=['pcb_stock'])
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=5)

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    design.refresh_from_db()
    assert design.pcb_stock == 15


@pytest.mark.django_db
def test_toggle_received_unmarking_subtracts_design_pcb_stock(client, staff_user, design):
    design.pcb_stock = 5
    design.save(update_fields=['pcb_stock'])
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=5, received=True)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert response.json() == {'ok': True, 'received': False}
    design.refresh_from_db()
    assert design.pcb_stock == 0


@pytest.mark.django_db
def test_toggle_received_logs_design_pcb_stock_history(client, staff_user, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=5)
    design.pcb_stock_history.all().delete()

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert list(design.pcb_stock_history.order_by('recorded_dt').values_list('stock', flat=True)) == [5]


@pytest.mark.django_db
def test_toggle_received_with_no_part_or_design_does_not_error(client, staff_user):
    # The "phantom entry" case (issue #100) - a JLCPCB line nobody has associated with a
    # Design yet (or deliberately never will, e.g. a superseded $0 line).
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, quantity=5)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_toggle_received', args=[line.pk]))

    assert response.json() == {'ok': True, 'received': True}


@pytest.mark.django_db
def test_receive_all_adds_quantities_to_design_pcb_stock(client, staff_user, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=4)
    PartsOrderLine.objects.create(parts_order=parts_order, quantity=7)  # unassociated - no effect

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))

    design.refresh_from_db()
    assert design.pcb_stock == 4


@pytest.mark.django_db
def test_receive_all_aggregates_multiple_lines_for_the_same_design(client, staff_user, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=3, supplier_line_number='1')
    PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=4, supplier_line_number='2')

    client.force_login(staff_user)
    client.post(reverse('erp:parts_order_receive_all', args=[parts_order.pk]))

    design.refresh_from_db()
    assert design.pcb_stock == 7


# --- parts_order_line_set_design (issue #100) ---

@pytest.mark.django_db
def test_set_design_associates_a_line(client, staff_user, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, quantity=1)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_set_design', args=[line.pk]), {'design_id': design.pk})

    assert response.json() == {'ok': True, 'design_id': design.pk, 'design_label': str(design)}
    line.refresh_from_db()
    assert line.design_id == design.pk


@pytest.mark.django_db
def test_set_design_clears_an_association_when_design_id_blank(client, staff_user, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, design=design, quantity=1)

    client.force_login(staff_user)
    response = client.post(reverse('erp:parts_order_line_set_design', args=[line.pk]), {'design_id': ''})

    assert response.json() == {'ok': True, 'design_id': None, 'design_label': ''}
    line.refresh_from_db()
    assert line.design_id is None


@pytest.mark.django_db
def test_set_design_requires_post(client, staff_user):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, quantity=1)

    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_line_set_design', args=[line.pk]))

    assert response.status_code == 405


@pytest.mark.django_db
def test_set_design_requires_staff(client, django_user_model, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    line = PartsOrderLine.objects.create(parts_order=parts_order, quantity=1)
    non_staff = django_user_model.objects.create_user(email='user@example.com', password='pass')
    client.force_login(non_staff)

    response = client.post(reverse('erp:parts_order_line_set_design', args=[line.pk]), {'design_id': design.pk})

    assert response.status_code == 302
    line.refresh_from_db()
    assert line.design_id is None


@pytest.mark.django_db
def test_parts_order_detail_renders_design_picker_for_jlcpcb_orders(client, staff_user, design):
    parts_order = PartsOrder.objects.create(supplier_name='JLCPCB', supplier_order_number='BATCH1')
    PartsOrderLine.objects.create(parts_order=parts_order, supplier_sku='PC1', quantity=1)

    client.force_login(staff_user)
    response = client.get(reverse('erp:parts_order_detail', args=[parts_order.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'design-picker-select' in content
    assert design.sku in content
