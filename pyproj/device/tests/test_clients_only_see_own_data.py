from datetime import datetime

from django.urls import reverse
from django.utils import timezone
import pytest

from device.forms import TestRecordForm
from device.models import Design, Device, DeviceEvent, TestRecord
from crm.models import Org


# Helper: Create two users, and some corresponding client, design and device data
@pytest.fixture
def create_users_and_user_data(django_user_model):
    client1 = Org(company_name='Client One', api_key='api-key-for-testing-1')
    client1.save()
    user1 = django_user_model.objects.create_user(email='user1@example.com', password='pass1')
    user1.client = client1
    user1.save()
    client1.users.add(user1)
    design1 = Design(client=client1, sku='C1A', name='Client One Design One', hw_version='1.0')
    design1.save()
    mothers_day = timezone.make_aware(datetime(2021, 5, 9, 20, 0, 0))  # May 9, 2021, 8:00 PM EAST
    device1 = Device(design=design1, creation_dt=mothers_day, notes='Pink soldermask')
    device1.save()

    client2 = Org(company_name='Client Two')
    client2.save()
    user2 = django_user_model.objects.create_user(email='user2@example.com', password='pass2')
    user2.client = client2
    user2.save()
    client2.users.add(user2)
    design2 = Design(client=client2, sku='C2A', name='Client Two Design One', hw_version='1.0')
    design2.save()
    halloween = timezone.make_aware(datetime(2021, 10, 31, 3, 0, 0))  # October 31, 2021, 3:00 AM AEDT
    device2 = Device(design=design2, creation_dt=halloween, notes='Yellow soldermask, black silkscreen')
    device2.save()

    results = {
        'user1': user1,
        'user1_device': device1,
        'user2': user2,
        'user2_device': device2,
        'api-key': client1.api_key,
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
    event_dt = timezone.make_aware(datetime(2021, 5, 10, 16, 20, 24))
    user1_device_event1 = DeviceEvent(
        device=user1_device, event_dt=event_dt, event_type='NOTE', description="User 1's first event"
    )
    user1_device_event1.save()
    user2 = data['user2']
    user2_device = data['user2_device']
    event_dt = timezone.make_aware(datetime(2021, 5, 11, 16, 20, 24))
    user2_device_event1 = DeviceEvent(
        device=user2_device,
        event_dt=event_dt,
        event_type='NOTE',
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


# Helper: Create some test records for two users
@pytest.fixture
def create_some_test_records(django_user_model, create_users_and_user_data):
    # Create a test record for user1, and a test record for user2
    data = create_users_and_user_data
    user1, user1_device, user2, user2_device = (data[k] for k in ('user1', 'user1_device', 'user2', 'user2_device'))
    user1_tr1 = TestRecord(
        device=user1_device,
        test_dt=timezone.make_aware(datetime(2021, 5, 10, 16, 20, 24)),
        notes="User 1's first test record",
    )
    user1_tr1.save()
    user2_tr1 = TestRecord(
        device=user2_device,
        test_dt=timezone.make_aware(datetime(2021, 5, 11, 16, 20, 24)),
        result='FAILED',
        notes="User 2's first test record",
    )
    user2_tr1.save()

    updates = {
        'user1_test_record1': user1_tr1,
        'user2_test_record1': user2_tr1,
    }

    data.update(updates)

    return data
