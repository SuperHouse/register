import pytest

from device.api import router, AuthByApiKey
from device.tests.test_api import TestClientWithAuth
from device.tests.test_clients_only_see_own_data import create_users_and_user_data
from ninja.testing import TestClient


@pytest.mark.django_db
def test_silly_noauth_fails():
    url = TestClientWithAuth.api_reverse('get_clients')
    client = TestClient(router)
    response = client.get(url)
    assert response.status_code == 401
    response = client.get(url, headers={})
    assert response.status_code == 401
    response = client.get(url, headers={AuthByApiKey.param_name: ''})
    assert response.status_code == 401


@pytest.mark.django_db
def test_silly_badauth_fails():
    api_client = TestClientWithAuth(router, 'not-a-valid-key')
    response = api_client.get('get_clients')
    assert response.status_code == 401


@pytest.mark.django_db
def test_silly_auth_passes(create_users_and_user_data):
    data = create_users_and_user_data

    api_client = TestClientWithAuth(router, data['api-key'])
    response = api_client.get('get_clients')
    assert response.status_code == 200
