from datetime import datetime

from django.urls import reverse
from django.utils import timezone
import pytest

from device.forms import TestRecordForm
from device.models import Client, Design, Device, DeviceEvent, TestRecord


# Helper: Create two users, and some corresponding client, design and device data
@pytest.fixture
def create_users_and_user_data(django_user_model):
    client1 = Client(company_name='Client One')
    client1.save()
    user1 = django_user_model.objects.create_user(email='user1@example.com', password='pass1')
    user1.client = client1
    user1.save()
    client1.users.add(user1)
    design1 = Design(client=client1, sku='C1A', name='Client One Design One', hw_version='1.0')
    design1.save()
    mothers_day = timezone.make_aware(datetime(2021, 5, 9))
    device1 = Device(design=design1, assembly_date=mothers_day, notes='Pink soldermask')
    device1.save()

    client2 = Client(company_name='Client Two')
    client2.save()
    user2 = django_user_model.objects.create_user(email='user2@example.com', password='pass2')
    user2.client = client2
    user2.save()
    client2.users.add(user2)
    design2 = Design(client=client2, sku='C2A', name='Client Two Design One', hw_version='1.0')
    design2.save()
    halloween = timezone.make_aware(datetime(2021, 10, 31))
    device2 = Device(design=design2, assembly_date=halloween, notes='Yellow soldermask, black silkscreen')
    device2.save()

    results = {
        'user1': user1,
        'user1_device': device1,
        'user2': user2,
        'user2_device': device2,
    }

    return results


# The 'device:device_detail' view should return 200 when pointed at a
# device owned by the user, and 404 if the device isn't owned by the user.


def test_user1_cant_see_user2_data(client, create_users_and_user_data):
    data = create_users_and_user_data
    client.force_login(data['user1'])
    response = client.get(reverse('device:device_detail', args=[data['user1_device'].pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_detail', args=[data['user2_device'].pk]))
    assert response.status_code == 404


# The 'device:device_detail' view should return 200 when pointed at any device.


def test_admin_can_see_user1_and_user2_data(admin_client, create_users_and_user_data):
    data = create_users_and_user_data
    response = admin_client.get(reverse('device:device_detail', args=[data['user1_device'].pk]))
    assert response.status_code == 200
    response = admin_client.get(reverse('device:device_detail', args=[data['user2_device'].pk]))
    assert response.status_code == 200


# Helper: Create some device events for two users
@pytest.fixture
def create_some_device_events(django_user_model, create_users_and_user_data):
    # Create a device event for user1, and a device event for user2
    data = create_users_and_user_data
    user1 = data['user1']
    user1_device = data['user1_device']
    event_dt = timezone.make_aware(datetime(2021, 5, 10))
    user1_device_event1 = DeviceEvent(device=user1_device, event_dt=event_dt, description="User 1's first event")
    user1_device_event1.save()
    user2 = data['user2']
    user2_device = data['user2_device']
    event_dt = timezone.make_aware(datetime(2021, 5, 11))
    user2_device_event1 = DeviceEvent(
        device=user2_device,
        event_dt=event_dt,
        description="User 2's first event",
        internal=True,
    )
    user2_device_event1.save()

    updates = {
        'user1_device_event1': user1_device_event1,
        'user2_device_event1': user2_device_event1,
    }

    data.update(updates)

    return data


def test_device_event_user1_cant_see_user2_data(client, create_some_device_events):
    data = create_some_device_events

    client.force_login(data['user1'])

    u1d = data['user1_device']
    u2d = data['user2_device']

    response = client.get(reverse('device:device_event_add', args=[u1d.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_event_add', args=[u2d.pk]))
    assert response.status_code == 404

    u1de = data['user1_device_event1']
    u2de = data['user2_device_event1']

    response = client.get(reverse('device:device_event_edit', args=[u1de.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_event_delete', args=[u1de.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_event_edit', args=[u2de.pk]))
    assert response.status_code == 404
    response = client.get(reverse('device:device_event_delete', args=[u2de.pk]))
    assert response.status_code == 404


# Helper: Create some test records for two users
@pytest.fixture
def create_some_test_records(django_user_model, create_users_and_user_data):
    # Create a test record for user1, and a test record for user2
    data = create_users_and_user_data
    user1, user1_device, user2, user2_device = (data[k] for k in ('user1', 'user1_device', 'user2', 'user2_device'))
    user1_tr1 = TestRecord(
        device=user1_device,
        test_dt=timezone.make_aware(datetime(2021, 5, 10)),
        notes="User 1's first test record",
    )
    user1_tr1.save()
    user2_tr1 = TestRecord(
        device=user2_device,
        test_dt=timezone.make_aware(datetime(2021, 5, 11)),
        result='SHIP',
        notes="User 2's first test record",
    )
    user2_tr1.save()

    updates = {
        'user1_test_record1': user1_tr1,
        'user2_test_record1': user2_tr1,
    }

    data.update(updates)

    return data


def test_test_record_user1_cant_see_user2_data(client, create_some_test_records):
    data = create_some_test_records

    client.force_login(data['user1'])

    u1d = data['user1_device']
    u2d = data['user2_device']

    response = client.get(reverse('device:test_record_add', args=[u1d.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:test_record_add', args=[u2d.pk]))
    assert response.status_code == 404

    u1tr = data['user1_test_record1']
    u2tr = data['user2_test_record1']

    response = client.get(reverse('device:test_record_edit', args=[u1tr.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:test_record_edit', args=[u2tr.pk]))
    assert response.status_code == 404
