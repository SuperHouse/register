from django.core.files.base import ContentFile
import pytest

from device.tests.test_api import TestClientWithAuth
from device.tests.test_clients_only_see_own_data import (
    create_users_and_user_data,
    staff_api_key,
)

from device.api import router
from device.models import DesignAsset


@pytest.fixture
def design_assets(create_users_and_user_data):
    """A PCB_TOP asset (visible to the owning org and to staff) and an internal ATTACHMENT
    asset (visible to staff only) on user1's design, plus a PCB_TOP asset on user2's design so
    org-scoping tests have something to confirm is excluded."""
    design1 = create_users_and_user_data['user1_device'].design
    design2 = create_users_and_user_data['user2_device'].design

    top = DesignAsset(design=design1, name='PCB Top', asset_type=DesignAsset.PCB_TOP)
    top.file.save('design1-top.png', ContentFile(b'top-image-bytes'), save=True)

    internal_doc = DesignAsset(design=design1, name='Internal Notes', asset_type=DesignAsset.ATTACHMENT, internal=True)
    internal_doc.file.save('design1-internal.txt', ContentFile(b'internal-bytes'), save=True)

    other_top = DesignAsset(design=design2, name='PCB Top', asset_type=DesignAsset.PCB_TOP)
    other_top.file.save('design2-top.png', ContentFile(b'other-top-bytes'), save=True)

    return {'design1': design1, 'top': top, 'internal_doc': internal_doc, 'other_top': other_top}


def test_list_design_assets_scoped_to_own_org(create_users_and_user_data, design_assets):
    api_client = TestClientWithAuth(router, create_users_and_user_data['api-key'])
    response = api_client.get('list_design_assets')
    assert response.status_code == 200

    ids = {entry['id'] for entry in response.json()}
    assert ids == {design_assets['top'].pk}
    assert design_assets['other_top'].pk not in ids


def test_list_design_assets_hides_internal_from_non_staff(create_users_and_user_data, design_assets):
    """internal=True means "do not show this asset to clients" - the same rule the web UI
    already applies, so the API must not leak it to a non-staff key either."""
    api_client = TestClientWithAuth(router, create_users_and_user_data['api-key'])
    response = api_client.get('list_design_assets')
    assert response.status_code == 200

    ids = {entry['id'] for entry in response.json()}
    assert design_assets['internal_doc'].pk not in ids


def test_list_design_assets_staff_sees_everything_including_internal(staff_api_key, design_assets):
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('list_design_assets')
    assert response.status_code == 200

    ids = {entry['id'] for entry in response.json()}
    assert ids == {design_assets['top'].pk, design_assets['internal_doc'].pk, design_assets['other_top'].pk}


def test_list_design_assets_filtered_by_design_and_type(staff_api_key, design_assets):
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('list_design_assets', params={
        'design_id': design_assets['design1'].pk,
        'asset_type': 'PCB_TOP',
    })
    assert response.status_code == 200

    entries = response.json()
    assert [entry['id'] for entry in entries] == [design_assets['top'].pk]
    assert entries[0]['asset_type'] == 'PCB_TOP'
    assert entries[0]['design_id'] == design_assets['design1'].pk


def test_download_design_asset_returns_file_content(create_users_and_user_data, design_assets):
    api_client = TestClientWithAuth(router, create_users_and_user_data['api-key'])
    response = api_client.get('download_design_asset', kwargs={'asset_id': design_assets['top'].pk})

    assert response.status_code == 200
    assert response['Content-Type'] == 'image/png'
    # NinjaResponse buffers a streaming response's content into .content on construction
    # (see ninja.testing.client.NinjaResponse) - .streaming_content itself is exhausted by then.
    assert response.content == b'top-image-bytes'


def test_download_design_asset_other_orgs_design_forbidden(create_users_and_user_data, design_assets):
    api_client = TestClientWithAuth(router, create_users_and_user_data['api-key'])
    response = api_client.get('download_design_asset', kwargs={'asset_id': design_assets['other_top'].pk})
    assert response.status_code == 403


def test_download_design_asset_internal_forbidden_for_non_staff(create_users_and_user_data, design_assets):
    api_client = TestClientWithAuth(router, create_users_and_user_data['api-key'])
    response = api_client.get('download_design_asset', kwargs={'asset_id': design_assets['internal_doc'].pk})
    assert response.status_code == 403


def test_download_design_asset_internal_allowed_for_staff(staff_api_key, design_assets):
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('download_design_asset', kwargs={'asset_id': design_assets['internal_doc'].pk})
    assert response.status_code == 200
    assert response.content == b'internal-bytes'


def test_download_design_asset_not_found(staff_api_key):
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('download_design_asset', kwargs={'asset_id': 999999})
    assert response.status_code == 404
