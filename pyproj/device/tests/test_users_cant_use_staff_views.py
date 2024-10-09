from django.urls import reverse

from test_clients_only_see_own_data import (
    create_users_and_user_data,
    create_some_device_events,
    create_some_test_records,
)


def test_users_cant_use_staff_views(
    create_users_and_user_data, create_some_test_records, create_some_device_events, client
):
    data = create_users_and_user_data

    customer = data['user1']

    # Users who are customers shouldn't be able to access this view
    client.force_login(customer)
    response = client.get(reverse('device:device_grid'))
    assert response.status_code == 302

    # Users who are customers shouldn't be able to amend data for their own devices
    u1d = data['user1_device']
    u1tr = create_some_test_records['user1_test_record1']
    u1de = create_some_device_events['user1_device_event1']

    response = client.get(reverse('device:device_event_add', args=[u1d.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:device_event_edit', args=[u1de.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:device_event_delete', args=[u1de.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:test_record_add', args=[u1d.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:test_record_edit', args=[u1tr.pk]))
    assert response.status_code == 302

    # They also shouldn't be able to amend data for other users' devices
    u2d = data['user2_device']
    u2tr = create_some_test_records['user2_test_record1']
    u2de = create_some_device_events['user2_device_event1']

    response = client.get(reverse('device:device_event_add', args=[u2d.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:device_event_edit', args=[u2de.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:device_event_delete', args=[u2de.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:test_record_add', args=[u2tr.pk]))
    assert response.status_code == 302
    response = client.get(reverse('device:test_record_edit', args=[u2tr.pk]))
    assert response.status_code == 302


# But users who are staff should.
def test_staff_can_use_staff_views(
    django_user_model, create_users_and_user_data, create_some_test_records, create_some_device_events, client
):
    # Create a staff user
    staff = django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)
    staff.save()
    client.force_login(staff)
    response = client.get(reverse('device:device_grid'))
    assert response.status_code == 200

    u1d = create_users_and_user_data['user1_device']
    u1tr = create_some_test_records['user1_test_record1']
    u1de = create_some_device_events['user1_device_event1']

    response = client.get(reverse('device:device_event_add', args=[u1d.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_event_edit', args=[u1de.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_event_delete', args=[u1de.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:test_record_add', args=[u1d.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:test_record_edit', args=[u1tr.pk]))
    assert response.status_code == 200

    # They also shouldn't be able to amend data for other users' devices
    u2d = create_users_and_user_data['user2_device']
    u2tr = create_some_test_records['user2_test_record1']
    u2de = create_some_device_events['user2_device_event1']

    response = client.get(reverse('device:device_event_add', args=[u2d.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_event_edit', args=[u2de.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:device_event_delete', args=[u2de.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:test_record_add', args=[u2d.pk]))
    assert response.status_code == 200
    response = client.get(reverse('device:test_record_edit', args=[u2tr.pk]))
    assert response.status_code == 200
