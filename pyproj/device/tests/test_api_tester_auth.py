import pytest
from django.db import IntegrityError

from device.api import router
from device.tests.test_api import TestClientWithAuth
from device.tests.test_clients_only_see_own_data import create_users_and_user_data
from device.models import DeviceEvent
from testing.models import Tester


@pytest.mark.django_db
def test_tester_api_key_authenticates_on_program_endpoint(create_users_and_user_data):
    data = create_users_and_user_data
    u1d = data['user1_device']

    tester = Tester.objects.create(name='Testomatic Bench 1')
    tester.regenerate_api_key()

    api_client = TestClientWithAuth(router, tester.api_key)
    response = api_client.post('post_device_program', kwargs={'device_pk': u1d.pk}, json={'sw_version': '1.0.0'})
    assert response.status_code == 200

    event = u1d.deviceevent_set.get(event_type='SW_VERSION')
    assert event.created_by_tester == tester
    assert event.created_by_user is None


@pytest.mark.django_db
def test_tester_key_rejected_on_user_only_endpoints(create_users_and_user_data):
    tester = Tester.objects.create(name='Testomatic Bench 1')
    tester.regenerate_api_key()

    api_client = TestClientWithAuth(router, tester.api_key)
    response = api_client.get('get_clients')
    assert response.status_code == 401


@pytest.mark.django_db
def test_deviceevent_single_creator_constraint(create_users_and_user_data):
    data = create_users_and_user_data
    u1d = data['user1_device']
    tester = Tester.objects.create(name='Testomatic Bench 1')

    event = DeviceEvent(device=u1d, event_type='NOTE', description='both set')
    event.created_by_user = data['user1']
    event.created_by_tester = tester

    with pytest.raises(IntegrityError):
        event.save()
