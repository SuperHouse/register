from django.urls import reverse

from test_clients_only_see_own_data import create_users_and_user_data


# client, create_some_device_events
def test_device_event_add_edit_delete(create_users_and_user_data, django_user_model, client):
    data = create_users_and_user_data

    customer = data['user1']

    # Create a staff user
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    staff.save()

    # Users who are customers shouldn't be able to access this view
    client.force_login(customer)
    response = client.get(reverse('device:device_add'))
    assert response.status_code == 302

    # But users who are staff should.
    client.force_login(staff)
    response = client.get(reverse('device:device_add'))
    assert response.status_code == 200
