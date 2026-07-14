from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from erp.models import Part, PartSource, PartSourceVariant


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
