"""Customers adding, editing and deleting their own notes on devices (register#7)."""
from django.urls import reverse
from django.utils import timezone
import pytest

from device.models import DeviceEvent

from test_clients_only_see_own_data import create_users_and_user_data  # noqa: F401 (fixture)


@pytest.fixture
def org_colleague(django_user_model, create_users_and_user_data):
    """A second customer user in user1's organisation."""
    data = create_users_and_user_data
    colleague = django_user_model.objects.create_user(email='colleague@example.com', password='pass3')
    data['user1_device'].design.client.users.add(colleague)
    return colleague


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user(email='staff@example.com', password='staffy', is_staff=True)


def make_event(device, description, user=None, **kwargs):
    event = DeviceEvent(device=device, description=description, **kwargs)
    event.set_creator(user=user)
    event.save()
    return event


def test_is_client_note(create_users_and_user_data, staff):
    data = create_users_and_user_data
    device = data['user1_device']
    assert make_event(device, 'customer', user=data['user1']).is_client_note is True
    assert make_event(device, 'staff', user=staff).is_client_note is False
    assert make_event(device, 'legacy').is_client_note is False
    assert make_event(device, 'fw', user=data['user1'], event_type=DeviceEvent.SW_VERSION).is_client_note is False
    assert make_event(device, 'hidden', user=data['user1'], internal=True).is_client_note is False


def test_customer_adds_a_note(client, create_users_and_user_data):
    data = create_users_and_user_data
    device = data['user1_device']
    client.force_login(data['user1'])

    page = client.get(reverse('device:device_event_add', args=[device.pk])).content.decode()
    # The customer form has no time, type or internal fields.
    assert 'name="event_dt"' not in page
    assert 'name="event_type"' not in page
    assert 'name="internal"' not in page

    # A customer can't set the time, make their note internal or another type, even by
    # posting the fields.
    before = timezone.now()
    response = client.post(reverse('device:device_event_add', args=[device.pk]), {
        'event_dt': '2020-01-01 10:00', 'description': 'Installed on truck ABC-123.',
        'event_type': 'SHIPPING', 'internal': 'on',
    })
    assert response.status_code == 302
    event = DeviceEvent.objects.get(description='Installed on truck ABC-123.')
    assert (event.device, event.event_type, event.internal) == (device, DeviceEvent.NOTE, False)
    assert event.event_dt >= before
    assert event.updated_dt is None
    assert event.created_by_user == data['user1']
    assert event.is_client_note


def test_colleague_in_same_org_can_edit_and_delete(client, create_users_and_user_data, org_colleague):
    data = create_users_and_user_data
    event = make_event(data['user1_device'], 'In camera kit #27.', user=data['user1'])
    client.force_login(org_colleague)

    original_dt = event.event_dt
    before = timezone.now()
    response = client.post(reverse('device:device_event_edit', args=[event.pk]), {
        'event_dt': '2020-01-01 09:30', 'description': 'In camera kit #28.',
    })
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.description == 'In camera kit #28.'
    # The original time and author are unchanged (a posted event_dt is ignored), and
    # the edit records its own time in updated_dt.
    assert event.event_dt == original_dt
    assert event.updated_dt >= before
    assert event.created_by_user == data['user1']

    response = client.post(reverse('device:device_event_delete', args=[event.pk]))
    assert response.status_code == 302
    assert not DeviceEvent.objects.filter(pk=event.pk).exists()


def test_customer_cannot_change_staff_or_system_events(client, create_users_and_user_data, staff):
    data = create_users_and_user_data
    device = data['user1_device']
    client.force_login(data['user1'])
    for event in [
        make_event(device, 'staff note', user=staff),
        make_event(device, 'legacy note'),
        make_event(device, 'v1.2', user=staff, event_type=DeviceEvent.SW_VERSION),
    ]:
        assert client.get(reverse('device:device_event_edit', args=[event.pk])).status_code == 403
        assert client.post(reverse('device:device_event_edit', args=[event.pk]), {
            'description': 'changed',
        }).status_code == 403
        assert client.post(reverse('device:device_event_delete', args=[event.pk])).status_code == 403
        event.refresh_from_db()
        assert event.description != 'changed'


def test_customer_cannot_touch_other_orgs_or_internal_events(client, create_users_and_user_data, staff):
    data = create_users_and_user_data
    other_org_note = make_event(data['user2_device'], 'user2 note', user=data['user2'])
    internal = make_event(data['user1_device'], 'internal', user=staff, internal=True)
    client.force_login(data['user1'])

    assert client.get(reverse('device:device_event_add', args=[data['user2_device'].pk])).status_code == 404
    for event in (other_org_note, internal):
        assert client.get(reverse('device:device_event_edit', args=[event.pk])).status_code == 404
        assert client.post(reverse('device:device_event_delete', args=[event.pk])).status_code == 404
    assert DeviceEvent.objects.filter(pk__in=[other_org_note.pk, internal.pk]).count() == 2


def test_staff_form_has_no_time_field(client, create_users_and_user_data, staff):
    client.force_login(staff)
    page = client.get(reverse('device:device_event_add', args=[create_users_and_user_data['user1_device'].pk]))
    assert 'name="event_dt"' not in page.content.decode()


def test_staff_can_edit_and_delete_customer_notes(client, create_users_and_user_data, staff):
    data = create_users_and_user_data
    event = make_event(data['user1_device'], 'Dropped it.', user=data['user1'])
    client.force_login(staff)

    response = client.post(reverse('device:device_event_edit', args=[event.pk]), {
        'event_type': 'NOTE', 'description': 'Dropped it (staff fixed typo).',
    })
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.description == 'Dropped it (staff fixed typo).'

    assert client.post(reverse('device:device_event_delete', args=[event.pk])).status_code == 302
    assert not DeviceEvent.objects.filter(pk=event.pk).exists()


def test_device_page_hides_internal_events_from_customers(client, create_users_and_user_data, staff):
    data = create_users_and_user_data
    device = data['user1_device']
    make_event(device, 'Secret staff-only remark', user=staff, internal=True)
    make_event(device, 'Public staff remark', user=staff)

    client.force_login(data['user1'])
    page = client.get(reverse('device:device_detail', args=[device.pk])).content.decode()
    assert 'Public staff remark' in page
    assert 'Secret staff-only remark' not in page

    client.force_login(staff)
    page = client.get(reverse('device:device_detail', args=[device.pk])).content.decode()
    assert 'Secret staff-only remark' in page


def test_device_page_shows_edit_buttons_only_for_manageable_events(client, create_users_and_user_data, staff):
    data = create_users_and_user_data
    device = data['user1_device']
    customer_note = make_event(device, 'customer', user=data['user1'])
    staff_note = make_event(device, 'staff', user=staff)

    client.force_login(data['user1'])
    page = client.get(reverse('device:device_detail', args=[device.pk])).content.decode()
    assert reverse('device:device_event_add', args=[device.pk]) in page
    assert reverse('device:device_event_edit', args=[customer_note.pk]) in page
    assert reverse('device:device_event_edit', args=[staff_note.pk]) not in page

    client.force_login(staff)
    page = client.get(reverse('device:device_detail', args=[device.pk])).content.decode()
    assert reverse('device:device_event_edit', args=[customer_note.pk]) in page
    assert reverse('device:device_event_edit', args=[staff_note.pk]) in page


def test_device_page_shows_last_changed_only_for_edited_events(client, create_users_and_user_data):
    data = create_users_and_user_data
    device = data['user1_device']
    edited = make_event(device, 'edited note', user=data['user1'])
    make_event(device, 'untouched note', user=data['user1'])
    client.force_login(data['user1'])
    client.post(reverse('device:device_event_edit', args=[edited.pk]), {'description': 'edited note v2'})

    page = client.get(reverse('device:device_detail', args=[device.pk])).content.decode()
    assert page.count('Changed ') == 1
