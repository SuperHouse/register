from django.urls import reverse
import pytest

from crm.models import Org
from device.models import Design
from erp.models import Batch, DesignBomEntry, Part


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Batch Parts Test Org')
    return Design.objects.create(client=org, sku='BPT1', name='Batch Parts Test Design', hw_version='1.0')


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


@pytest.mark.django_db
def test_parts_required_multiplies_per_board_quantity_by_batch_quantity(client, staff_user, design):
    r10k = Part.objects.create(name='10k Resistor', value='10k', package='0402', device='RES')
    cap = Part.objects.create(name='100nF Cap', value='100nF', package='0603', device='CAP')

    # Two 10k resistors per board (R1, R2), one capacitor (C1).
    DesignBomEntry.objects.create(design=design, part=r10k, reference='R1')
    DesignBomEntry.objects.create(design=design, part=r10k, reference='R2')
    DesignBomEntry.objects.create(design=design, part=cap, reference='C1')

    batch = Batch.objects.create(design=design, quantity=30)

    client.force_login(staff_user)
    response = client.get(reverse('erp:batch_edit', args=[batch.pk]))
    content = response.content.decode()

    def row(name):
        idx = content.find(name)
        start = content.rfind('<tr', 0, idx)
        end = content.find('</tr>', idx)
        return content[start:end]

    assert '<td>60</td>' in row('10k Resistor')
    assert '<td>30</td>' in row('100nF Cap')

    # Neither part has any sources, so Available has no known stock level -> shown as "-".
    assert '-' in row('10k Resistor')
    assert '-' in row('100nF Cap')


@pytest.mark.django_db
def test_parts_required_one_row_per_part_not_per_placement(client, staff_user, design):
    r10k = Part.objects.create(name='10k Resistor', value='10k')
    DesignBomEntry.objects.create(design=design, part=r10k, reference='R1')
    DesignBomEntry.objects.create(design=design, part=r10k, reference='R2')
    DesignBomEntry.objects.create(design=design, part=r10k, reference='R3')

    batch = Batch.objects.create(design=design, quantity=10)

    client.force_login(staff_user)
    response = client.get(reverse('erp:batch_edit', args=[batch.pk]))
    content = response.content.decode()

    assert content.count('10k Resistor') == 1
    assert '<td>30</td>' in content


@pytest.mark.django_db
def test_parts_required_columns(client, staff_user, design):
    part = Part.objects.create(name='10k Resistor', value='10k', package='0402', device='RES', stock=7)
    DesignBomEntry.objects.create(design=design, part=part, reference='R1')

    batch = Batch.objects.create(design=design, quantity=10)

    client.force_login(staff_user)
    response = client.get(reverse('erp:batch_edit', args=[batch.pk]))
    content = response.content.decode()

    assert '<th>Part</th>' in content
    assert '<th>Qty</th>' in content
    assert '<th>Stock</th>' in content
    assert '<th>Available</th>' in content
    assert '<th>Value</th>' not in content
    assert '<th>Package</th>' not in content
    assert '<th>Device</th>' not in content

    idx = content.find('10k Resistor')
    start = content.rfind('<tr', 0, idx)
    end = content.find('</tr>', idx)
    row = content[start:end]
    assert '<td>10</td>' in row
    assert '<td>7</td>' in row


@pytest.mark.django_db
def test_parts_required_empty_when_design_has_no_bom(client, staff_user, design):
    batch = Batch.objects.create(design=design, quantity=10)

    client.force_login(staff_user)
    response = client.get(reverse('erp:batch_edit', args=[batch.pk]))
    content = response.content.decode()

    assert 'This design has no BOM entries, so no parts are required.' in content
