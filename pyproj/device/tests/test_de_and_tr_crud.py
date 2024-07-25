from datetime import datetime

from django.urls import reverse
from django.utils import timezone

from device.models import DeviceEvent, TestRecord

from test_clients_only_see_own_data import (
    create_some_device_events,
    create_some_test_records,
    create_users_and_user_data,
)

post_dt_fmt = '%Y-%m-%d %H:%M:%S'


def test_device_event_add_edit_delete(client, create_some_device_events):
    data = create_some_device_events

    client.force_login(data['user1'])

    u1d = data['user1_device']
    u1de = data['user1_device_event1']
    old_de_dt = u1de.event_dt

    assert u1de.internal == False
    fields = ('internal', 'description')
    data = {f: getattr(u1de, f) for f in fields}
    data['internal'] = True
    data['event_dt'] = datetime.now().strftime(post_dt_fmt)
    response = client.post(reverse('device:device_event_edit', args=[u1de.pk]), data)
    assert response.status_code == 302

    updated_u1de = DeviceEvent.objects.get(pk=u1de.pk)
    assert updated_u1de.pk == u1de.pk
    assert updated_u1de.internal == True
    assert updated_u1de.event_dt != old_de_dt

    assert u1d.deviceevent_set.count() == 1
    data = {
        'event_dt': datetime.now().strftime(post_dt_fmt),
        'event_type': 'NOTE',
        'description': 'Billed on invoice 31',
    }
    response = client.post(reverse('device:device_event_add', args=[u1d.pk]), data)
    assert response.status_code == 302
    assert u1d.deviceevent_set.count() == 2

    new_de_set = u1d.deviceevent_set.exclude(pk=u1de.pk)
    assert new_de_set.count() == 1
    new_de = new_de_set.first()
    assert new_de.internal == False
    assert new_de.description == data['description']

    response = client.post(reverse('device:device_event_delete', args=[new_de.pk]))
    assert response.status_code == 302
    assert u1d.deviceevent_set.count() == 1


def test_test_record_add_edit(client, create_some_test_records):
    data = create_some_test_records

    client.force_login(data['user1'])

    u1d = data['user1_device']
    u1tr = data['user1_test_record1']
    old_tr_dt = u1tr.test_dt

    assert u1tr.result == TestRecord.NEW

    new_test_dt_str = '2023-06-05 12:34:56'
    new_test_dt = timezone.make_aware(datetime.strptime(new_test_dt_str, post_dt_fmt))
    fields = ('result', 'notes')
    data = {f: getattr(u1tr, f) for f in fields}
    data['result'] = 'FAIL'
    data['test_dt'] = new_test_dt_str
    response = client.post(reverse('device:test_record_edit', args=[u1tr.pk]), data)
    assert response.status_code == 302

    updated_u1tr = TestRecord.objects.get(pk=u1tr.pk)
    assert updated_u1tr.pk == u1tr.pk
    assert updated_u1tr.result == TestRecord.FAIL
    assert updated_u1tr.test_dt == new_test_dt

    assert u1d.testrecord_set.count() == 1
    msg = 'This blew up the smokerator!'
    data = {
        'result': 'FAIL',
        'test_dt': new_test_dt_str,
        'notes': msg,
    }
    response = client.post(reverse('device:test_record_add', args=[u1d.pk]), data)
    assert response.status_code == 302
    assert u1d.testrecord_set.count() == 2

    new_tr_set = u1d.testrecord_set.exclude(pk=u1tr.pk)
    assert new_tr_set.count() == 1
    new_tr = new_tr_set.first()
    assert new_tr.result == TestRecord.FAIL
    assert new_tr.notes == msg
