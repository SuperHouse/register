from django.urls import reverse
import pytest

from crm.models import Org
from device.models import Design
from erp.models import Batch, DesignBomEntry, Part


@pytest.fixture
def two_orgs_with_batches(django_user_model):
    org1 = Org.objects.create(company_name='Batch Access Org One')
    user1 = django_user_model.objects.create_user(email='org1user@example.com', password='pass1')
    org1.users.add(user1)
    design1 = Design.objects.create(client=org1, sku='BAO1', name='Org One Design', hw_version='1.0')
    batch1 = Batch.objects.create(design=design1, quantity=5, po='PO-ORG1')

    org2 = Org.objects.create(company_name='Batch Access Org Two')
    user2 = django_user_model.objects.create_user(email='org2user@example.com', password='pass2')
    org2.users.add(user2)
    design2 = Design.objects.create(client=org2, sku='BAO2', name='Org Two Design', hw_version='1.0')
    batch2 = Batch.objects.create(design=design2, quantity=7, po='PO-ORG2')

    staff = django_user_model.objects.create_user(email='staffbatch@example.com', password='staffy', is_staff=True)

    return {
        'user1': user1, 'batch1': batch1, 'design1': design1,
        'user2': user2, 'batch2': batch2, 'design2': design2,
        'staff': staff,
    }


@pytest.mark.django_db
def test_non_staff_can_load_batch_list(client, two_orgs_with_batches):
    client.force_login(two_orgs_with_batches['user1'])
    response = client.get(reverse('erp:batch_list'))
    assert response.status_code == 200


@pytest.mark.django_db
def test_non_staff_batch_list_scoped_to_own_org(client, two_orgs_with_batches):
    client.force_login(two_orgs_with_batches['user1'])
    response = client.get(reverse('erp:batch_list'))
    content = response.content.decode()
    assert 'PO-ORG1' in content
    assert 'PO-ORG2' not in content


@pytest.mark.django_db
def test_staff_batch_list_sees_all_orgs(client, two_orgs_with_batches):
    client.force_login(two_orgs_with_batches['staff'])
    response = client.get(reverse('erp:batch_list'))
    content = response.content.decode()
    assert 'PO-ORG1' in content
    assert 'PO-ORG2' in content


@pytest.mark.django_db
def test_non_staff_batch_list_data_scoped(client, two_orgs_with_batches):
    data = two_orgs_with_batches
    client.force_login(data['user1'])
    response = client.get(reverse('erp:batch_list_data'))
    assert response.status_code == 200
    ids = [b['id'] for b in response.json()['batches']]
    assert data['batch1'].pk in ids
    assert data['batch2'].pk not in ids


@pytest.mark.django_db
def test_non_staff_can_view_own_batch_detail(client, two_orgs_with_batches):
    data = two_orgs_with_batches
    client.force_login(data['user1'])
    response = client.get(reverse('erp:batch_edit', args=[data['batch1'].pk]))
    assert response.status_code == 200
    assert 'PO-ORG1' in response.content.decode()


@pytest.mark.django_db
def test_non_staff_cannot_view_other_orgs_batch_detail(client, two_orgs_with_batches):
    data = two_orgs_with_batches
    client.force_login(data['user1'])
    response = client.get(reverse('erp:batch_edit', args=[data['batch2'].pk]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_non_staff_batch_detail_hides_edit_and_costing(client, two_orgs_with_batches):
    data = two_orgs_with_batches
    part = Part.objects.create(name='10k Resistor', value='10k')
    DesignBomEntry.objects.create(design=data['design1'], part=part, reference='R1')

    client.force_login(data['user1'])
    response = client.get(reverse('erp:batch_edit', args=[data['batch1'].pk]))
    content = response.content.decode()

    # No editable form for design/quantity/po/notes.
    assert 'Save Changes' not in content
    # Staff-only cost/stock data must not be exposed to non-staff.
    assert 'Parts Required' not in content
    assert 'Build Costing' not in content
    # Staff-only mutating actions must not be exposed either.
    assert reverse('erp:batch_duplicate', args=[data['batch1'].pk]) not in content
    assert reverse('erp:batch_production_stage_add', args=[data['batch1'].pk]) not in content


@pytest.mark.django_db
def test_staff_batch_detail_shows_edit_and_costing(client, two_orgs_with_batches):
    data = two_orgs_with_batches
    part = Part.objects.create(name='10k Resistor', value='10k')
    DesignBomEntry.objects.create(design=data['design1'], part=part, reference='R1')

    client.force_login(data['staff'])
    response = client.get(reverse('erp:batch_edit', args=[data['batch1'].pk]))
    content = response.content.decode()

    assert 'Save Changes' in content
    assert 'Parts Required' in content
    assert 'Build Costing' in content


@pytest.mark.django_db
def test_non_staff_sidebar_shows_batches_and_designs_links(client, two_orgs_with_batches):
    client.force_login(two_orgs_with_batches['user1'])
    response = client.get(reverse('dashboard'))
    content = response.content.decode()
    assert reverse('erp:batch_list') in content
    assert reverse('design_list') in content


@pytest.mark.django_db
def test_non_staff_dashboard_batch_count_scoped(client, two_orgs_with_batches):
    client.force_login(two_orgs_with_batches['user1'])
    response = client.get(reverse('dashboard'))
    assert response.context['batch_count'] == 1
