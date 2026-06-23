import datetime
import io
from PIL import Image
from urllib.parse import urlencode

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from ninja import NinjaAPI
from ninja.testing import TestClient

from device.tests.test_clients_only_see_own_data import (
    create_users_and_user_data,
    create_some_test_records,
)

from device.api import router
from device.models import Device


def dt_as_utc_in_json(dt):
    return dt.astimezone(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


class TestClientWithAuth(TestClient):
    api_prefix = 'api-1.0.0'
    api_root = reverse(f'{api_prefix}:api-root')

    def __init__(self, router, api_key):
        super().__init__(router)
        self.api_key = api_key

    def get(self, endpoint, params=None, kwargs=None, **other_args):
        url = self.api_reverse(endpoint, kwargs)
        if params:
            url = ''.join((url, '?', urlencode(params)))
        headers = other_args.pop('headers', {})
        headers['X-API-Key'] = self.api_key

        return super().get(url, headers=headers, **other_args)

    def post(self, endpoint, kwargs=None, **other_args):
        url = self.api_reverse(endpoint, kwargs)
        headers = other_args.pop('headers', {})
        headers['X-API-Key'] = self.api_key

        return super().post(url, headers=headers, **other_args)

    @classmethod
    def api_reverse(cls, endpoint, kwargs=None):
        label2 = f'{cls.api_prefix}:{endpoint}'
        url = reverse(label2, kwargs=kwargs)

        return url.replace(cls.api_root, '')


def test_list_clients(create_users_and_user_data):
    data = create_users_and_user_data

    u1c = data['user1'].client
    u2c = data['user2'].client

    api_client = TestClientWithAuth(router, data['api-key'])
    response = api_client.get('get_clients')
    assert response.status_code == 200

    expected_json = [
        {'id': u1c.pk, 'company_name': u1c.company_name},
        {'id': u2c.pk, 'company_name': u2c.company_name},
    ]
    actual_json = response.json()

    assert actual_json == expected_json


def test_list_all_designs(create_users_and_user_data):
    data = create_users_and_user_data

    u1c = data['user1'].client
    u2c = data['user2'].client
    u1design = data['user1_device'].design
    u2design = data['user2_device'].design

    api_client = TestClientWithAuth(router, data['api-key'])
    response = api_client.get('get_designs')
    assert response.status_code == 200

    expected_json = [
        {
            'client': {'id': u1c.pk, 'company_name': u1c.company_name},
            'id': u1design.pk,
            'sku': u1design.sku,
            'name': u1design.name,
            'hw_version': u1design.hw_version,
            'description': None,
        },
        {
            'client': {'id': u2c.pk, 'company_name': u2c.company_name},
            'id': u2design.pk,
            'sku': u2design.sku,
            'name': u2design.name,
            'hw_version': u2design.hw_version,
            'description': None,
        },
    ]
    actual_json = response.json()

    assert actual_json == expected_json


def test_list_designs_for_client(create_users_and_user_data):
    data = create_users_and_user_data

    u2c = data['user2'].client
    u2design = data['user2_device'].design

    api_client = TestClientWithAuth(router, data['api-key'])
    response = api_client.get('get_designs', params={'client_pk': str(u2c.pk)})
    assert response.status_code == 200

    expected_json = [
        {
            'client': {'id': u2c.pk, 'company_name': u2c.company_name},
            'id': u2design.pk,
            'sku': u2design.sku,
            'name': u2design.name,
            'hw_version': u2design.hw_version,
            'description': None,
        },
    ]
    actual_json = response.json()

    assert actual_json == expected_json


def test_get_existing_device(create_users_and_user_data):
    data = create_users_and_user_data

    u2d = data['user2_device']

    api_client = TestClientWithAuth(router, data['api-key'])
    response = api_client.get('get_existing_device', kwargs={'device_pk': u2d.pk})
    assert response.status_code == 200

    expected_json = {
        'design_pk': u2d.design.pk,
        'creation_dt': dt_as_utc_in_json(u2d.creation_dt),
    }
    actual_json = response.json()

    assert actual_json == expected_json


def test_get_nonexistent_device_fails(create_users_and_user_data):
    data = create_users_and_user_data

    u2d = data['user2_device']

    api_client = TestClientWithAuth(router, data['api-key'])
    fictional_pk = u2d.first_free_serial()

    response = api_client.get('get_existing_device', kwargs={'device_pk': fictional_pk})
    assert response.status_code == 404


def test_add_or_update_device(create_users_and_user_data):
    data = create_users_and_user_data

    u2d = data['user2_device']
    u1design = data['user1_device'].design

    api_client = TestClientWithAuth(router, data['api-key'])

    # Test that we get a 400 for an existing device,
    # but with a design that doesn't exist
    data = {
        'pk': u2d.pk,
        'design_pk': 999,
    }
    response = api_client.post('add_or_update_device', json=data)
    assert response.status_code == 400

    # For a device that already exists, test that the creation date changes
    # if the creation date is not provided (because it's set to now)
    data = {
        'pk': u2d.pk,
        'design_pk': u2d.design.pk,
    }
    response = api_client.post('add_or_update_device', json=data)
    assert response.status_code == 200
    new_u2d = Device.objects.get(pk=u2d.pk)
    assert new_u2d.creation_dt != u2d.creation_dt

    # For a device that already exists, test that we can
    # change the design
    data = {
        'pk': u2d.pk,
        'design_pk': u1design.pk,
    }
    response = api_client.post('add_or_update_device', json=data)
    new_u2d = Device.objects.get(pk=u2d.pk)
    assert new_u2d.design.pk == u1design.pk

    # For a device that already exists, test that we can
    # set the creation date
    day_after = u2d.creation_dt + datetime.timedelta(days=1)
    data = {
        'pk': u2d.pk,
        'design_pk': u2d.design.pk,
        'creation_dt': dt_as_utc_in_json(day_after),
    }
    response = api_client.post('add_or_update_device', json=data)
    assert response.status_code == 200
    new_u2d = Device.objects.get(pk=u2d.pk)
    assert new_u2d.creation_dt == day_after

    # For a device that doesn't exist, test that we can create it
    new_pk = u2d.first_free_serial()
    data = {
        'pk': new_pk,
        'design_pk': u2d.design.pk,
    }
    response = api_client.post('add_or_update_device', json=data)
    assert response.status_code == 201

    new_u2d = Device.objects.get(pk=new_pk)
    assert new_u2d.design.pk == u2d.design.pk


def test_program_device(create_users_and_user_data):
    sw_version_a = '1.2.3a'
    sw_version_b = '3.1.4b'

    data = create_users_and_user_data

    u2d = data['user2_device']

    api_client = TestClientWithAuth(router, data['api-key'])

    # Test that a non-existent device returns 404
    new_pk = Device.first_free_serial()
    data = {
        'sw_version': sw_version_a,
    }

    response = api_client.post('post_device_program', kwargs={'device_pk': new_pk}, json=data)
    assert response.status_code == 404

    # Test that an existing device has no software version
    assert u2d.latest_sw_version() is None

    # Test that we can add a software version to the device
    response = api_client.post('post_device_program', kwargs={'device_pk': u2d.pk}, json=data)
    assert response.status_code == 200
    new_u2d = Device.objects.get(pk=u2d.pk)
    assert new_u2d.latest_sw_version() == sw_version_a

    # Test that we can add another software version to the device
    data = {
        'sw_version': sw_version_b,
    }
    response = api_client.post('post_device_program', kwargs={'device_pk': u2d.pk}, json=data)
    assert response.status_code == 200
    new_u2d = Device.objects.get(pk=u2d.pk)
    assert new_u2d.latest_sw_version() == sw_version_b

    # The device should now have two versions
    assert new_u2d.deviceevent_set.filter(event_type='SW_VERSION').count() == 2
    assert new_u2d.deviceevent_set.get(event_type='SW_VERSION', description=sw_version_a)
    assert new_u2d.deviceevent_set.get(event_type='SW_VERSION', description=sw_version_b)

    # Test that adding an existing software version to the device creates a dupe.
    data = {
        'sw_version': sw_version_a,
    }
    response = api_client.post('post_device_program', kwargs={'device_pk': u2d.pk}, json=data)
    assert response.status_code == 200
    new_u2d = Device.objects.get(pk=u2d.pk)
    # The device should now have three versions
    sw_versions = new_u2d.deviceevent_set.filter(event_type='SW_VERSION')
    assert sw_versions.count() == 3
    # First and last sw versions should be the same (1.2.3a)
    assert sw_versions.first().description == sw_version_a
    assert sw_versions.last().description == sw_version_a


def test_add_test_record(create_users_and_user_data):
    data = create_users_and_user_data

    u2d = data['user2_device']

    api_client = TestClientWithAuth(router, data['api-key'])

    # Test that a non-existent device returns 404
    new_pk = Device.first_free_serial()
    day_after = u2d.creation_dt + datetime.timedelta(days=1)

    data = {
        'result': 'PASS',
        'test_dt': dt_as_utc_in_json(day_after),
        'notes': 'Results nominal',
    }

    response = api_client.post('add_test_record', kwargs={'device_pk': new_pk}, json=data)
    assert response.status_code == 404

    # Test that an existing device has no test records
    assert u2d.testrecord_set.count() == 0

    # Test that an invalid test type causes a fault
    data['result'] = 'SILLY'
    response = api_client.post('add_test_record', kwargs={'device_pk': u2d.pk}, json=data)
    assert response.status_code == 422
    assert u2d.testrecord_set.count() == 0

    # Test that we can add a test record to the device
    data['result'] = 'PASS'
    response = api_client.post('add_test_record', kwargs={'device_pk': u2d.pk}, json=data)
    assert response.status_code == 200
    new_u2d = Device.objects.get(pk=u2d.pk)
    assert u2d.testrecord_set.count() == 1
    new_tr = new_u2d.testrecord_set.first()
    expected_json = {
        'pk': new_tr.pk,
    }
    actual_json = response.json()
    assert actual_json == expected_json
    assert new_tr.result == data['result'] and new_tr.test_dt == day_after and new_tr.notes == data['notes']


def test_add_image_to_test_record(create_some_test_records):
    def generate_tinypic():
        f = io.BytesIO()  # Storage in memory
        img = Image.new('RGB', (10, 10), 'white')
        img.save(f, format='png')
        f.name = 'test.png'
        f.seek(0)

        return f

    data = create_some_test_records

    u2tr = data['user2_test_record1']

    api_client = TestClientWithAuth(router, data['api-key'])

    img = generate_tinypic()
    uploaded_file = SimpleUploadedFile('test.png', img.read(), content_type='image/png')
    data = {}

    # Test that adding an image to a non-existent test record fails
    response = api_client.post(
        'add_test_image',
        kwargs={'testrecord_pk': 999999},
        data=data,
        FILES={'file': uploaded_file},
    )
    assert response.status_code == 404

    # Test that an existing test record has no test images
    assert u2tr.testimage_set.count() == 0

    # Test that we can add a test image to the test record
    response = api_client.post(
        'add_test_image', kwargs={'testrecord_pk': u2tr.pk}, data=data, FILES={'file': uploaded_file}
    )
    assert response.status_code == 200

    # Did the test record acquire an image?
    ti_set = u2tr.testimage_set.all()
    assert ti_set.count() == 1
    new_ti = ti_set.first()

    # The response json should give a url for the thumbnail.  It's too hard to
    # say what the path is (because filenames are mangled), so just confirm that
    # a thumbnail path is in the response.
    actual_json = response.json()
    assert len(actual_json) == 1
    assert 'thumbnail' in actual_json

    # Is the image data the same?
    img_data = new_ti.image.file.open().read()
    assert len(img_data) > 0
    assert len(img_data) == len(img.getbuffer())
    assert img_data == img.getbuffer()

    # Remove the saved image file from storage
    new_ti.image.delete()


def test_add_device_image(create_users_and_user_data):
    def generate_tinypic():
        f = io.BytesIO()
        img = Image.new('RGB', (10, 10), 'white')
        img.save(f, format='png')
        f.name = 'test.png'
        f.seek(0)

        return f

    data = create_users_and_user_data

    u1d = data['user1_device']
    u2d = data['user2_device']
    user2 = data['user2']
    user2.api_key = 'api-key-for-testing-2'
    user2.save()

    user1_client = TestClientWithAuth(router, data['api-key'])
    user2_client = TestClientWithAuth(router, user2.api_key)

    # A user can add an image to a device belonging to their own org
    uploaded_file = SimpleUploadedFile('test.png', generate_tinypic().read(), content_type='image/png')
    response = user1_client.post(
        'add_device_image', kwargs={'device_pk': u1d.pk}, data={'notes': 'Nominal'}, FILES={'file': uploaded_file}
    )
    assert response.status_code == 200
    assert u1d.deviceimage_set.count() == 1

    # A user can't add an image to a device belonging to a different org
    uploaded_file = SimpleUploadedFile('test.png', generate_tinypic().read(), content_type='image/png')
    response = user2_client.post(
        'add_device_image', kwargs={'device_pk': u1d.pk}, data={'notes': 'Nominal'}, FILES={'file': uploaded_file}
    )
    assert response.status_code == 403
    assert u1d.deviceimage_set.count() == 1

    # A user can add an image to a device belonging to their own org (sanity check on user2/device2)
    uploaded_file = SimpleUploadedFile('test.png', generate_tinypic().read(), content_type='image/png')
    response = user2_client.post(
        'add_device_image', kwargs={'device_pk': u2d.pk}, data={'notes': 'Nominal'}, FILES={'file': uploaded_file}
    )
    assert response.status_code == 200
    assert u2d.deviceimage_set.count() == 1
