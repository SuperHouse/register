from datetime import datetime
import pytest

from django.utils import timezone
from django.urls import reverse


from device.models import Client, Design, Device


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
