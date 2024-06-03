from django.urls import reverse

from device.models import DeviceEvent

from test_clients_only_see_own_data import create_some_device_events, create_users_and_user_data


def test_device_event_add_edit_delete(client, create_some_device_events):
    data = create_some_device_events

    client.force_login(data['user1'])

    u1d = data['user1_device']
    u1de = data['user1_device_event1']
    old_de_dt = u1de.event_dt

    assert u1de.internal == False
    # , content_type="application/x-www-form-urlencoded"
    # data = urlencode({"something": "something"})
    fields = ('internal', 'event_type', 'description')
    data = {f: getattr(u1de, f) for f in fields}
    data['internal'] = True
    response = client.post(reverse('device:device_event_edit', args=[u1de.pk]), data)
    assert response.status_code == 302

    updated_u1de = DeviceEvent.objects.get(pk=u1de.pk)
    assert updated_u1de.pk == u1de.pk
    assert updated_u1de.internal == True
    assert updated_u1de.event_dt != old_de_dt

    assert u1d.deviceevent_set.count() == 1
    msg = 'Billed on invoice 31'
    data = {
        'event_type': 'INV',
        'description': msg,
    }
    response = client.post(reverse('device:device_event_add', args=[u1d.pk]), data)
    assert response.status_code == 302
    assert u1d.deviceevent_set.count() == 2

    new_de_set = u1d.deviceevent_set.exclude(pk=u1de.pk)
    assert new_de_set.count() == 1
    new_de = new_de_set.first()
    assert new_de.internal == False
    assert new_de.event_type == 'INV'
    assert new_de.description == msg

    response = client.post(reverse('device:device_event_delete', args=[new_de.pk]))
    assert response.status_code == 302
    assert u1d.deviceevent_set.count() == 1
