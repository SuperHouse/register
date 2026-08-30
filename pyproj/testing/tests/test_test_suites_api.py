import io
import json
import zipfile
from datetime import datetime

import pytest

from device.tests.test_api import TestClientWithAuth
from device.tests.test_clients_only_see_own_data import (
    create_users_and_user_data,
    staff_api_key,
)

from testing.api import router
from testing.models import TestSuite


@pytest.fixture
def two_suites(create_users_and_user_data):
    """Two versions of one Test Suite Package on the same design used by the shared
    create_users_and_user_data fixture - issue #116's list/download endpoints aren't org-scoped
    (they're staff-only, not per-client), so which client the design belongs to doesn't matter
    here beyond reusing the fixture other API tests already share. v1 is SAVED (finalised) and
    v2 is a DRAFT on top of it - the realistic "someone's mid-edit on the next version" shape -
    so tests can confirm the DRAFT-exclusion policy below without needing a separate fixture."""
    design = create_users_and_user_data['user1_device'].design
    v1 = TestSuite.objects.create(design=design, version=1, status=TestSuite.SAVED)
    v2 = TestSuite.objects.create(design=design, version=2, status=TestSuite.DRAFT)
    return {'design': design, 'v1': v1, 'v2': v2}


def test_list_test_suites_requires_staff(create_users_and_user_data, two_suites):
    api_client = TestClientWithAuth(router, create_users_and_user_data['api-key'])
    response = api_client.get('list_test_suites')
    assert response.status_code == 403


def test_list_test_suites_excludes_drafts(staff_api_key, two_suites):
    """A Testomatic tester must never see a Test Suite Package that's still a DRAFT - only a
    finalised (SAVED) version is fit to run, since a draft can still change mid-edit. v2 (DRAFT)
    is deliberately left out of the expected result here."""
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('list_test_suites')
    assert response.status_code == 200

    design = two_suites['design']
    v1 = two_suites['v1']
    entries = response.json()

    assert [{k: v for k, v in entry.items() if k != 'created_dt'} for entry in entries] == [
        {'id': v1.pk, 'design_id': design.pk, 'version': 1, 'status': 'SAVED'},
    ]
    # sqlite (used in tests) only stores datetimes to millisecond precision, so compare with
    # microseconds dropped rather than expecting an exact round-trip match.
    actual_dt = datetime.fromisoformat(entries[0]['created_dt']).replace(microsecond=0)
    assert actual_dt == v1.created_dt.replace(microsecond=0)


def test_list_test_suites_filtered_by_design(staff_api_key, two_suites, create_users_and_user_data):
    other_design = create_users_and_user_data['user2_device'].design
    other_saved = TestSuite.objects.create(design=other_design, version=1, status=TestSuite.SAVED)

    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('list_test_suites', params={'design_id': two_suites['design'].pk})
    assert response.status_code == 200
    ids = {entry['id'] for entry in response.json()}
    assert ids == {two_suites['v1'].pk}
    assert other_saved.pk not in ids


def test_download_test_suite_requires_staff(create_users_and_user_data, two_suites):
    api_client = TestClientWithAuth(router, create_users_and_user_data['api-key'])
    response = api_client.get('download_test_suite', kwargs={'suite_id': two_suites['v1'].pk})
    assert response.status_code == 403


def test_download_test_suite_not_found(staff_api_key, two_suites):
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('download_test_suite', kwargs={'suite_id': 999999})
    assert response.status_code == 404


def test_download_test_suite_refuses_draft(staff_api_key, two_suites):
    """Even a staff key can't download a DRAFT - the policy is "not finalised yet", not an
    access-control gap, so there's no bypass for staff here."""
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('download_test_suite', kwargs={'suite_id': two_suites['v2'].pk})
    assert response.status_code == 403
    assert 'draft' in response.json()['message'].lower()


def test_download_test_suite_returns_same_package_as_the_ui_download(staff_api_key, two_suites):
    """The API's download endpoint reuses build_test_suite_package_response() - the same helper
    the "Download" link on the Design detail page's Test Suite tab uses - so the archive shape
    matches exactly (see testing.views.test_suite_download, issue #114)."""
    suite = two_suites['v1']
    api_client = TestClientWithAuth(router, staff_api_key)
    response = api_client.get('download_test_suite', kwargs={'suite_id': suite.pk})

    assert response.status_code == 200
    assert response['Content-Type'] == 'application/zip'

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    [name] = [n for n in archive.namelist() if n.endswith('test-suite-definition.json')]
    data = json.loads(archive.read(name))
    assert data['test_suite']['id'] == suite.pk
    assert data['test_suite']['version'] == suite.version
