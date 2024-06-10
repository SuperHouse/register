from django.urls import reverse

from test_clients_only_see_own_data import (
    create_users_and_user_data,
)


def test_device_search(client, admin_client, create_users_and_user_data):
    data = create_users_and_user_data

    client.force_login(data['user1'])
    u1d = data['user1_device']
    u1d_pk = u1d.pk
    u2d = data['user2_device']
    u2d_pk = u2d.pk

    # Empty search
    response = client.get(reverse('device:device_search'), {})
    assert response.status_code == 200  # Found, so redirect to detail page
    t = response.content.decode()
    assert 'Device search' in t
    assert 'no board with that serial number' not in t

    # Search for a device that exists
    response = client.get(reverse('device:device_search'), {'q': str(u1d_pk)})
    assert response.status_code == 302  # Found, so redirect to detail page
    assert response.url == reverse('device:device_detail', args=[u1d_pk])

    # Search for a device that does not exist
    response = client.get(reverse('device:device_search'), {'q': '99990'})
    assert response.status_code == 200  # Not found, so go to search page
    assert 'no board with that serial number' in response.content.decode()

    # Search for a device that belongs to someone else
    u2d = data['user2_device']
    u2d_pk = u2d.pk
    response = client.get(reverse('device:device_search'), {'q': str(u2d_pk)})
    assert response.status_code == 200  # Not found, so go to search page
    assert 'no board with that serial number' in response.content.decode()

    # Admin can see both boards
    response = admin_client.get(reverse('device:device_search'), {'q': str(u1d_pk)})
    assert response.status_code == 302  # Found, so redirect to detail page
    assert response.url == reverse('device:device_detail', args=[u1d_pk])
    response = admin_client.get(reverse('device:device_search'), {'q': str(u2d_pk)})
    assert response.status_code == 302  # Found, so redirect to detail page
    assert response.url == reverse('device:device_detail', args=[u2d_pk])
