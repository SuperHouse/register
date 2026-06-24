from django.urls import reverse

from device.tests.test_clients_only_see_own_data import create_users_and_user_data


def test_non_staff_cant_use_user_management_views(create_users_and_user_data, client):
    data = create_users_and_user_data
    customer = data['user1']
    other_user = data['user2']

    client.force_login(customer)

    response = client.get(reverse('user_list'))
    assert response.status_code == 302

    response = client.get(reverse('user_add'))
    assert response.status_code == 302

    response = client.get(reverse('user_edit', args=[other_user.pk]))
    assert response.status_code == 302

    response = client.post(reverse('user_regenerate_key', args=[other_user.pk]))
    assert response.status_code == 302


def test_staff_can_use_user_management_views(django_user_model, create_users_and_user_data, client):
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    client.force_login(staff)

    data = create_users_and_user_data
    other_user = data['user2']

    response = client.get(reverse('user_list'))
    assert response.status_code == 200

    response = client.get(reverse('user_add'))
    assert response.status_code == 200

    response = client.get(reverse('user_edit', args=[other_user.pk]))
    assert response.status_code == 200

    old_api_key = other_user.api_key
    response = client.post(reverse('user_regenerate_key', args=[other_user.pk]))
    assert response.status_code == 302
    other_user.refresh_from_db()
    assert other_user.api_key is not None
    assert other_user.api_key != old_api_key
