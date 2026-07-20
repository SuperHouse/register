from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from erp.models import Part, PartCategory, PartsOrder, PartsOrderLine, PartSource, PartSourceVariant, parse_component_value


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.mark.django_db
def test_has_stale_source_data_false_when_no_sources():
    part = Part.objects.create(name='No sources', value='1')
    assert part.has_stale_source_data is False


@pytest.mark.django_db
def test_has_stale_source_data_true_when_never_refreshed():
    part = Part.objects.create(name='Never refreshed', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC')
    PartSourceVariant.objects.create(source=source, supplier_sku='SKU1', last_refreshed=None)
    assert part.has_stale_source_data is True


@pytest.mark.django_db
def test_has_stale_source_data_false_when_recently_refreshed():
    part = Part.objects.create(name='Fresh', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC')
    PartSourceVariant.objects.create(source=source, supplier_sku='SKU1', last_refreshed=timezone.now())
    assert part.has_stale_source_data is False


@pytest.mark.django_db
def test_has_stale_source_data_true_when_refreshed_over_48h_ago():
    part = Part.objects.create(name='Stale', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC')
    PartSourceVariant.objects.create(
        source=source, supplier_sku='SKU1', last_refreshed=timezone.now() - timedelta(hours=49)
    )
    assert part.has_stale_source_data is True


@pytest.mark.django_db
def test_has_stale_source_data_true_when_any_variant_is_stale():
    part = Part.objects.create(name='Mixed', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC')
    PartSourceVariant.objects.create(source=source, supplier_sku='FRESH', last_refreshed=timezone.now())
    PartSourceVariant.objects.create(
        source=source, supplier_sku='STALE', last_refreshed=timezone.now() - timedelta(hours=72)
    )
    assert part.has_stale_source_data is True


@pytest.mark.django_db
def test_part_source_has_stale_variant_data():
    part = Part.objects.create(name='Mixed sources', value='1')

    fresh_source = PartSource.objects.create(part=part, supplier_name='LCSC')
    PartSourceVariant.objects.create(source=fresh_source, supplier_sku='F1', last_refreshed=timezone.now())
    assert fresh_source.has_stale_variant_data is False

    stale_source = PartSource.objects.create(part=part, supplier_name='DigiKey')
    PartSourceVariant.objects.create(
        source=stale_source, supplier_sku='S1', last_refreshed=timezone.now() - timedelta(hours=72)
    )
    assert stale_source.has_stale_variant_data is True

    never_source = PartSource.objects.create(part=part, supplier_name='Mouser')
    PartSourceVariant.objects.create(source=never_source, supplier_sku='N1', last_refreshed=None)
    assert never_source.has_stale_variant_data is True

    empty_source = PartSource.objects.create(part=part, supplier_name='Element14')
    assert empty_source.has_stale_variant_data is False


# --- PartSource.save() stock history logging ---

@pytest.mark.django_db
def test_save_logs_history_on_creation():
    part = Part.objects.create(name='Fresh source', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=100)
    assert list(source.stock_history.values_list('stock', flat=True)) == [100]


@pytest.mark.django_db
def test_save_logs_history_when_stock_changes():
    part = Part.objects.create(name='Changing stock', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=100)

    source.stock = 50
    source.save(update_fields=['stock'])

    assert list(source.stock_history.order_by('recorded_dt').values_list('stock', flat=True)) == [100, 50]


@pytest.mark.django_db
def test_save_does_not_duplicate_history_on_unchanged_stock():
    part = Part.objects.create(name='Stable stock', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=100)

    source.stock = 100
    source.save(update_fields=['stock'])

    assert source.stock_history.count() == 1


@pytest.mark.django_db
def test_save_self_heals_missing_history_on_unchanged_stock():
    # Simulate a listing that predates the stock-history feature (or was created via a
    # path that bypasses save(), e.g. loaddata/import_data): stock is set, but there's no
    # PartSourceStockHistory row for it at all.
    part = Part.objects.create(name='Historyless', value='1')
    source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=100)
    source.stock_history.all().delete()
    assert source.stock_history.count() == 0

    source.stock = 100  # unchanged - a naive "did it change" check alone wouldn't log this
    source.save(update_fields=['stock'])

    assert list(source.stock_history.values_list('stock', flat=True)) == [100]


@pytest.mark.django_db
def test_part_edit_shows_stale_warning_per_source(client, staff_user):
    STALE_TITLE = 'Stock has never been refreshed, or not refreshed in over 48 hours'

    part = Part.objects.create(name='Multi', value='1')

    fresh_source = PartSource.objects.create(part=part, supplier_name='LCSC', stock=100)
    PartSourceVariant.objects.create(source=fresh_source, supplier_sku='F1', last_refreshed=timezone.now())

    stale_source = PartSource.objects.create(part=part, supplier_name='DigiKey', stock=50)
    PartSourceVariant.objects.create(
        source=stale_source, supplier_sku='S1', last_refreshed=timezone.now() - timedelta(hours=72)
    )

    never_source = PartSource.objects.create(part=part, supplier_name='Mouser', stock=20)
    PartSourceVariant.objects.create(source=never_source, supplier_sku='N1', last_refreshed=None)

    client.force_login(staff_user)
    response = client.get(reverse('erp:part_edit', args=[part.pk]))
    content = response.content.decode()

    # Search from the Sources card onward, since the supplier names also appear earlier
    # on the page inside the Stock History chart's embedded JSON data.
    sources_start = content.find('<strong>Sources</strong>')

    def row(name):
        idx = content.find(name, sources_start)
        start = content.rfind('<tr', 0, idx)
        end = content.find('</tr>', idx)
        return content[start:end]

    assert STALE_TITLE not in row('LCSC')
    assert STALE_TITLE in row('DigiKey')
    assert STALE_TITLE in row('Mouser')


@pytest.mark.django_db
def test_part_list_shows_warning_icons(client, staff_user):
    STALE_TITLE = 'Stock has never been refreshed, or not refreshed in over 48 hours'

    no_source_part = Part.objects.create(name='NoSourcePart', value='1')

    stale_part = Part.objects.create(name='StalePart', value='2')
    stale_source = PartSource.objects.create(part=stale_part, supplier_name='LCSC')
    PartSourceVariant.objects.create(
        source=stale_source, supplier_sku='SKU1', last_refreshed=timezone.now() - timedelta(hours=50)
    )

    never_refreshed_part = Part.objects.create(name='NeverRefreshedPart', value='4')
    never_refreshed_source = PartSource.objects.create(part=never_refreshed_part, supplier_name='LCSC')
    PartSourceVariant.objects.create(source=never_refreshed_source, supplier_sku='SKU3', last_refreshed=None)

    fresh_part = Part.objects.create(name='FreshPart', value='3')
    fresh_source = PartSource.objects.create(part=fresh_part, supplier_name='LCSC')
    PartSourceVariant.objects.create(source=fresh_source, supplier_sku='SKU2', last_refreshed=timezone.now())

    client.force_login(staff_user)
    response = client.get(reverse('erp:part_list'))
    content = response.content.decode()

    def row(name):
        idx = content.find(name)
        start = content.rfind('<tr', 0, idx)
        end = content.find('</tr>', idx)
        return content[start:end]

    assert 'No sources listed' in row('NoSourcePart')
    assert STALE_TITLE not in row('NoSourcePart')

    assert 'No sources listed' not in row('StalePart')
    assert STALE_TITLE in row('StalePart')

    assert 'No sources listed' not in row('NeverRefreshedPart')
    assert STALE_TITLE in row('NeverRefreshedPart')

    assert 'No sources listed' not in row('FreshPart')
    assert STALE_TITLE not in row('FreshPart')


@pytest.mark.django_db
def test_part_stock_field_defaults_to_none():
    part = Part.objects.create(name='No stock set', value='1')
    assert part.stock is None


@pytest.mark.django_db
def test_part_list_shows_stock_column(client, staff_user):
    Part.objects.create(name='WithStock', value='1', stock=42)
    Part.objects.create(name='NoStock', value='2')

    client.force_login(staff_user)
    response = client.get(reverse('erp:part_list'))
    content = response.content.decode()

    assert '<th>Stock</th>' in content

    def row(name):
        idx = content.find(name)
        start = content.rfind('<tr', 0, idx)
        end = content.find('</tr>', idx)
        return content[start:end]

    assert '<td>42</td>' in row('WithStock')
    assert '<td>-</td>' in row('NoStock')


@pytest.mark.django_db
def test_part_edit_form_saves_stock(client, staff_user):
    part = Part.objects.create(name='EditStock', value='1')

    client.force_login(staff_user)
    response = client.post(reverse('erp:part_edit', args=[part.pk]), {
        'name': 'EditStock', 'description': '', 'category': '', 'device': '', 'package': '',
        'value': '1', 'fusion_library': '', 'stock': '15',
    })
    assert response.status_code == 302

    part.refresh_from_db()
    assert part.stock == 15


# --- issue #89: Incoming Stock / Committed Stock ---

@pytest.mark.django_db
def test_incoming_stock_zero_and_committed_stock_none_with_no_orders():
    part = Part.objects.create(name='No incoming/committed set', value='1')
    assert part.incoming_stock == 0
    assert part.committed_stock is None


@pytest.mark.django_db
def test_incoming_stock_sums_not_received_lines_excludes_received_and_cancelled():
    part = Part.objects.create(name='Tracked Part', value='1')
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=5, received=False)
    PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=3, received=True)
    PartsOrderLine.objects.create(
        parts_order=parts_order, part=part, quantity=2, received=False, status=PartsOrderLine.CANCELLED,
    )

    assert part.incoming_stock == 5


@pytest.mark.django_db
def test_incoming_stock_counts_shipped_lines_not_yet_received():
    # A SHIPPED line is still "incoming" until someone marks it received - status alone
    # doesn't clear it, only the received flag does.
    part = Part.objects.create(name='In Transit Part', value='1')
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(
        parts_order=parts_order, part=part, quantity=10, received=False, status=PartsOrderLine.SHIPPED,
    )

    assert part.incoming_stock == 10


@pytest.mark.django_db
def test_part_list_shows_incoming_column(client, staff_user):
    with_incoming = Part.objects.create(name='WithIncoming', value='1')
    Part.objects.create(name='NoIncoming', value='2')
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(parts_order=parts_order, part=with_incoming, quantity=7, received=False)

    client.force_login(staff_user)
    response = client.get(reverse('erp:part_list'))
    content = response.content.decode()

    assert '<th>Incoming</th>' in content

    def row(name):
        idx = content.find(name)
        start = content.rfind('<tr', 0, idx)
        end = content.find('</tr>', idx)
        return content[start:end]

    assert '<td>7</td>' in row('WithIncoming')
    assert '<td>0</td>' in row('NoIncoming')


@pytest.mark.django_db
def test_part_edit_shows_incoming_stock_read_only_and_committed_field(client, staff_user):
    part = Part.objects.create(name='EditFields', value='1')
    parts_order = PartsOrder.objects.create(supplier_name='DigiKey', supplier_order_number='SO1')
    PartsOrderLine.objects.create(parts_order=parts_order, part=part, quantity=4, received=False)

    client.force_login(staff_user)
    response = client.get(reverse('erp:part_edit', args=[part.pk]))
    content = response.content.decode()

    assert 'Incoming Stock' in content
    assert '<p class="form-control-plaintext" title="Sum of quantities on order but not yet marked received, across all known supplier orders">4</p>' in content
    assert 'Committed Stock' in content
    # No editable Incoming Stock input - only Committed Stock should be a number input in the form.
    assert 'name="incoming_stock"' not in content


@pytest.mark.django_db
def test_part_edit_form_saves_committed_stock_and_ignores_incoming_stock_post_data(client, staff_user):
    part = Part.objects.create(name='EditIncomingCommitted', value='1')

    client.force_login(staff_user)
    response = client.post(reverse('erp:part_edit', args=[part.pk]), {
        'name': 'EditIncomingCommitted', 'description': '', 'category': '', 'device': '', 'package': '',
        'value': '1', 'fusion_library': '', 'incoming_stock': '25', 'committed_stock': '10',
    })
    assert response.status_code == 302

    part.refresh_from_db()
    assert part.committed_stock == 10
    assert part.incoming_stock == 0


# --- issue #87: numeric sort of Part.value engineering notation ---

@pytest.mark.parametrize('raw, expected', [
    ('5.1K', 5100.0),
    ('5K1', 5100.0),
    ('49R9', 49.9),
    ('100K', 100000.0),
    ('100R', 100.0),
    ('10K', 10000.0),
    ('10M', 10000000.0),
    ('10R', 10.0),
    ('120R', 120.0),
    ('12K4', 12400.0),
    ('0R', 0.0),
    ('0R DNP', 0.0),
    ('10K DNP', 10000.0),
    ('220uF 35V', 2.2e-4),
    ('100uH 2.1A', 1e-4),
    ('500mA 1206 PTC', 0.5),
    ('48MHz', 48000000.0),
    ('15A Mini Blade', 15.0),
    ('1nF', 1e-9),
    ('22pF', 22e-12),
    ('47.5K', 47500.0),
    ('49', 49.0),
    ('49.9', 49.9),
    ('18650', 18650.0),
])
def test_parse_component_value_parses(raw, expected):
    assert parse_component_value(raw) == pytest.approx(expected)


@pytest.mark.parametrize('raw', [
    '1N4004', '2N2222A', '2N2907A', '2N7002', '74HC2G125', '74LVC1G125GV', 'AP2112K-3.3', '', None,
])
def test_parse_component_value_unparseable(raw):
    assert parse_component_value(raw) is None


@pytest.mark.django_db
def test_value_sort_key_orders_by_magnitude():
    values = ['100K', '100R', '10K', '10M', '10R', '120R', '12K4']
    parts = [Part.objects.create(name=v, value=v) for v in values]
    ordered = sorted(parts, key=lambda p: p.value_sort_key)
    assert [p.value for p in ordered] == ['10R', '100R', '120R', '10K', '12K4', '100K', '10M']


@pytest.mark.django_db
def test_value_sort_key_bare_number_sorts_as_literal_ohms():
    r44 = Part.objects.create(name='44R', value='44R')
    bare = Part.objects.create(name='Bare 49', value='49')
    decimal = Part.objects.create(name='Bare 49.9', value='49.9')
    r55 = Part.objects.create(name='55R', value='55R')
    ordered = sorted([r55, decimal, bare, r44], key=lambda p: p.value_sort_key)
    assert [p.value for p in ordered] == ['44R', '49', '49.9', '55R']


@pytest.mark.django_db
def test_value_sort_key_unparseable_sorts_after_parsed_values():
    junk = Part.objects.create(name='Diode', value='1N4004')
    real = Part.objects.create(name='Resistor', value='10K')
    ordered = sorted([junk, real], key=lambda p: p.value_sort_key)
    assert [p.name for p in ordered] == ['Resistor', 'Diode']


@pytest.mark.django_db
def test_value_sort_key_ties_on_equal_value_break_on_name():
    b = Part.objects.create(name='B - 0603', value='10K')
    a = Part.objects.create(name='A - 0402', value='10K')
    ordered = sorted([b, a], key=lambda p: p.value_sort_key)
    assert [p.name for p in ordered] == ['A - 0402', 'B - 0603']


@pytest.mark.django_db
def test_part_list_orders_by_value_magnitude(client, staff_user):
    category = PartCategory.objects.create(name='Resistors')
    Part.objects.create(name='R-100K', value='100K', category=category)
    Part.objects.create(name='R-100R', value='100R', category=category)
    Part.objects.create(name='R-10K', value='10K', category=category)

    client.force_login(staff_user)
    response = client.get(reverse('erp:part_list'))
    content = response.content.decode()

    assert content.index('R-100R') < content.index('R-10K') < content.index('R-100K')


@pytest.mark.django_db
def test_grouped_part_choice_field_orders_by_value_magnitude():
    from erp.forms import GroupedPartChoiceField

    category = PartCategory.objects.create(name='Resistors')
    p100k = Part.objects.create(name='R-100K', value='100K', category=category)
    p100r = Part.objects.create(name='R-100R', value='100R', category=category)
    p10k = Part.objects.create(name='R-10K', value='10K', category=category)

    field = GroupedPartChoiceField(queryset=Part.objects.select_related('category'))
    choices = dict(field.choices)

    assert [pk for pk, _ in choices['Resistors']] == [p100r.pk, p10k.pk, p100k.pk]
