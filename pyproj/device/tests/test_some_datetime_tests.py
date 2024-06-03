from datetime import datetime

from django.urls import reverse
from django.utils import timezone
import pytest

from device.forms import TestRecordForm
from device.models import TestRecord

from test_clients_only_see_own_data import create_users_and_user_data


def test_datetimes_are_saved_correctly(client, create_users_and_user_data):
    data = create_users_and_user_data

    client.force_login(data['user1'])

    # Does datetime get preserved through ORM save process?
    tz = timezone.get_current_timezone()
    dt = timezone.make_aware(datetime(2024, 4, 21, 10, 42, 1))
    tr = TestRecord(device=data['user1_device'], result='PASS', notes='Test notes', test_dt=dt)
    tr.save()
    tr_ = TestRecord.objects.get(pk=tr.pk)

    assert tr.test_dt == dt
    assert tr.test_dt == tr_.test_dt

    post = {
        'device': '1',
        'result': 'PASS',
        'notes': 'Test notes',
        'test_dt': '2024-04-21 10:42:01',
    }

    # Does datetime get preserved through form save process?
    form = TestRecordForm(post, instance=tr_)
    valid = form.is_valid()
    assert valid
    form.save()
    assert tr.test_dt == tr_.test_dt

    # Does datetime get preserved through web request and view process?
    fields = ('device', 'result', 'notes', 'test_dt')
    data = {f: getattr(tr_, f) for f in fields}
    data['device'] = data['device'].pk
    data['test_dt'] = '2024-04-21 10:42:01'
    response = client.post(reverse('device:test_record_edit', args=[tr_.pk]), post)
    assert response.status_code == 302

    tr_ = TestRecord.objects.get(pk=tr.pk)
    assert tr_.test_dt == tr.test_dt
    assert tr.test_dt == dt
