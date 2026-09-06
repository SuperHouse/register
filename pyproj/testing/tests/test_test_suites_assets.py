import io
import json
import os
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils.text import slugify

from crm.models import Org
from device.models import Design
from testing.models import TestStep, TestStepAsset, TestSuite


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Isolates every test in this file to its own throwaway MEDIA_ROOT. Without this, real
    files land under the project's actual media/ directory (same as dev) and persist across
    test runs; since SQLite can reuse autoincrement pks after a rolled-back transaction, a
    later test's step can collide with a same-named file a much earlier run left behind at the
    same test_step_assets/<id>/ path, spuriously triggering storage's own collision-rename and
    breaking the exact-filename assertions these tests make."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='asset-staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def plain_user(django_user_model):
    return django_user_model.objects.create_user(email='asset-plain@example.com', password='plainy')


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Asset Test Org')
    return Design.objects.create(client=org, sku='AT1', name='Asset Test Design', hw_version='1.0')


@pytest.fixture
def suite(design):
    return TestSuite.objects.create(design=design, version=1, status=TestSuite.DRAFT)


@pytest.fixture
def avrdude_step(suite):
    return TestStep.objects.create(
        suite=suite, step_type=TestStep.UPLOAD_FIRMWARE_AVRDUDE, name='Program',
        config={'port': '/dev/ttyUSB0', 'programmer_type': 'arduino', 'mcu': 'atmega328p', 'schema_version': 1},
    )


@pytest.fixture
def esptool_step(suite):
    return TestStep.objects.create(
        suite=suite, step_type=TestStep.UPLOAD_FIRMWARE_ESPTOOL, name='Program',
        config={'port': '/dev/ttyUSB0', 'chip': 'esp32', 'schema_version': 1},
    )


def _bin(name):
    return SimpleUploadedFile(name, b'\x00\x01binary-data', content_type='application/octet-stream')


@pytest.mark.django_db
def test_asset_filename_property(avrdude_step):
    asset = TestStepAsset.objects.create(step=avrdude_step, file=_bin('main.hex'))
    assert asset.filename == 'main.hex'


@pytest.mark.django_db
def test_add_firmware_file_syncs_config(client, staff_user, avrdude_step):
    client.force_login(staff_user)
    response = client.post(
        reverse('testing:test_step_asset_add', args=[avrdude_step.pk]),
        {'file': _bin('main.hex')},
    )
    assert response.status_code == 302

    avrdude_step.refresh_from_db()
    assert avrdude_step.config['firmware_file'] == 'main.hex'
    assert avrdude_step.assets.count() == 1


@pytest.mark.django_db
def test_uploading_a_second_firmware_file_replaces_the_first(client, staff_user, avrdude_step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})
    old_asset = avrdude_step.assets.get()
    old_path = old_asset.file.path

    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('other.hex')})

    avrdude_step.refresh_from_db()
    assert avrdude_step.assets.count() == 1  # only ever one firmware file for this type
    assert avrdude_step.config['firmware_file'] == 'other.hex'
    assert not TestStepAsset.objects.filter(pk=old_asset.pk).exists()
    assert not os.path.exists(old_path)  # the old file was removed from disk, not just the row


@pytest.mark.django_db
def test_add_esptool_image_requires_address(client, staff_user, esptool_step):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_step_asset_add', args=[esptool_step.pk]), {'file': _bin('app.bin')})
    assert response.status_code == 302
    esptool_step.refresh_from_db()
    assert esptool_step.assets.count() == 0


@pytest.mark.django_db
def test_esptool_images_accumulate_and_sync_config_in_order(client, staff_user, esptool_step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[esptool_step.pk]),
                {'file': _bin('bootloader.bin'), 'address': '0x1000'})
    client.post(reverse('testing:test_step_asset_add', args=[esptool_step.pk]),
                {'file': _bin('app.bin'), 'address': '0x10000'})

    esptool_step.refresh_from_db()
    assert esptool_step.assets.count() == 2
    assert esptool_step.config['images'] == [
        {'address': '0x1000', 'file': 'bootloader.bin'},
        {'address': '0x10000', 'file': 'app.bin'},
    ]


@pytest.mark.django_db
def test_re_adding_same_esptool_filename_replaces_just_that_image(client, staff_user, esptool_step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[esptool_step.pk]),
                {'file': _bin('bootloader.bin'), 'address': '0x1000'})
    client.post(reverse('testing:test_step_asset_add', args=[esptool_step.pk]),
                {'file': _bin('app.bin'), 'address': '0x10000'})
    client.post(reverse('testing:test_step_asset_add', args=[esptool_step.pk]),
                {'file': _bin('bootloader.bin'), 'address': '0x2000'})  # replace, new address

    esptool_step.refresh_from_db()
    assert esptool_step.assets.count() == 2
    assert esptool_step.config['images'] == [
        {'address': '0x10000', 'file': 'app.bin'},
        {'address': '0x2000', 'file': 'bootloader.bin'},
    ]


@pytest.mark.django_db
def test_cross_step_filename_clash_is_refused(client, staff_user, suite, avrdude_step):
    other_step = TestStep.objects.create(
        suite=suite, step_type=TestStep.UPLOAD_FIRMWARE_OPENOCD, name='Program 2',
        config={'interface_config': 'interface/stlink.cfg', 'target_config': 'target/stm32f4x.cfg', 'schema_version': 1},
    )
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})

    response = client.post(reverse('testing:test_step_asset_add', args=[other_step.pk]), {'file': _bin('main.hex')})
    assert response.status_code == 302

    other_step.refresh_from_db()
    assert other_step.assets.count() == 0  # refused - main.hex already belongs to avrdude_step
    avrdude_step.refresh_from_db()
    assert avrdude_step.assets.count() == 1


@pytest.mark.django_db
def test_delete_asset_syncs_config(client, staff_user, avrdude_step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})
    asset = avrdude_step.assets.get()

    response = client.post(reverse('testing:test_step_asset_delete', args=[asset.pk]))
    assert response.status_code == 302

    avrdude_step.refresh_from_db()
    assert avrdude_step.assets.count() == 0
    assert 'firmware_file' not in avrdude_step.config


@pytest.mark.django_db
def test_asset_views_require_staff(client, plain_user, avrdude_step):
    client.force_login(plain_user)
    add_response = client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})
    assert add_response.status_code == 302
    assert avrdude_step.assets.count() == 0


@pytest.mark.django_db
def test_adding_an_asset_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, avrdude_step):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})
    assert response.status_code == 302

    # The original SAVED step/suite are untouched.
    avrdude_step.refresh_from_db()
    assert avrdude_step.assets.count() == 0
    suite.refresh_from_db()
    assert suite.status == TestSuite.SAVED

    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    new_step = draft.steps.get()
    assert new_step.assets.get().filename == 'main.hex'


@pytest.mark.django_db
def test_fork_draft_duplicates_asset_bytes_independently(client, staff_user, design, suite, avrdude_step):
    """Editing a copy's asset must never touch the original SAVED version's file (issue #121
    follow-up) - _fork_draft physically duplicates the bytes rather than sharing storage."""
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})
    original_asset = avrdude_step.assets.get()
    original_path = original_asset.file.path

    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])

    # Uploading again now forks a new draft first, then replaces *its* copy of the asset.
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('replacement.hex')})

    draft = design.test_suites.first()
    assert draft.version == 2
    # The original SAVED asset's file must still exist untouched.
    assert os.path.exists(original_path)
    original_asset.refresh_from_db()
    assert original_asset.filename == 'main.hex'


@pytest.mark.django_db
def test_copy_steps_from_copies_assets(client, staff_user, design, suite, avrdude_step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])

    org2 = Org.objects.create(company_name='Asset Test Org 2')
    dest_design = Design.objects.create(client=org2, sku='AT2', name='Dest Design', hw_version='1.0')

    response = client.post(reverse('testing:test_suite_copy_steps_from', args=[dest_design.pk]),
                            {'source_design': design.pk})
    assert response.status_code == 302

    dest_suite = dest_design.test_suites.first()
    dest_step = dest_suite.steps.get()
    assert dest_step.assets.get().filename == 'main.hex'
    assert dest_step.config['firmware_file'] == 'main.hex'
    # The copy is an independent file, not a shared reference.
    assert dest_step.assets.get().pk != avrdude_step.assets.get().pk


@pytest.mark.django_db
def test_copy_steps_from_skips_clashing_filename_and_resyncs_config(client, staff_user, design, suite, avrdude_step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])

    org2 = Org.objects.create(company_name='Asset Test Org 3')
    dest_design = Design.objects.create(client=org2, sku='AT3', name='Dest Design 2', hw_version='1.0')
    dest_suite = TestSuite.objects.create(design=dest_design, version=1, status=TestSuite.DRAFT)
    existing_step = TestStep.objects.create(
        suite=dest_suite, step_type=TestStep.UPLOAD_FIRMWARE_OPENOCD, name='Existing',
        config={'interface_config': 'a', 'target_config': 'b', 'schema_version': 1},
    )
    TestStepAsset.objects.create(step=existing_step, file=_bin('main.hex'))

    response = client.post(reverse('testing:test_suite_copy_steps_from', args=[dest_design.pk]),
                            {'source_design': design.pk})
    assert response.status_code == 302

    copied_step = dest_suite.steps.get(name='Program')
    assert copied_step.assets.count() == 0
    assert 'firmware_file' not in copied_step.config  # resynced away since the copy was skipped


@pytest.mark.django_db
def test_download_bundles_asset_bytes_in_package(client, staff_user, avrdude_step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_asset_add', args=[avrdude_step.pk]), {'file': _bin('main.hex')})

    design = avrdude_step.suite.design
    response = client.get(reverse('testing:test_suite_download', args=[design.pk]))
    archive = zipfile.ZipFile(io.BytesIO(response.content))

    package_name = f'{slugify(design.sku)}-hw{slugify(design.hw_version)}-test-suite-v{avrdude_step.suite.version}'
    names = archive.namelist()
    assert f'{package_name}/test-suite-definition.json' in names
    assert f'{package_name}/main.hex' in names
    assert archive.read(f'{package_name}/main.hex') == b'\x00\x01binary-data'

    definition = json.loads(archive.read(f'{package_name}/test-suite-definition.json'))
    assert definition['test_steps'][0]['config']['firmware_file'] == 'main.hex'
