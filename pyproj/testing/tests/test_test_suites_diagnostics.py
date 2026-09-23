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
from testing.models import TestStep, TestStepDiagnosticImage, TestSuite


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Isolates every test in this file to its own throwaway MEDIA_ROOT - see the identical
    fixture in test_test_suites_assets.py for why."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='diag-staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def plain_user(django_user_model):
    return django_user_model.objects.create_user(email='diag-plain@example.com', password='plainy')


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Diagnostic Test Org')
    return Design.objects.create(client=org, sku='DT1', name='Diagnostic Test Design', hw_version='1.0')


@pytest.fixture
def suite(design):
    return TestSuite.objects.create(design=design, version=1, status=TestSuite.DRAFT)


@pytest.fixture
def step(suite):
    return TestStep.objects.create(
        suite=suite, step_type=TestStep.READ_RAIL_VOLTAGE, name='Check 5V',
        config={'rail': '5V', 'min_v': 4.8, 'max_v': 5.2, 'schema_version': 1},
    )


def _img(name):
    # A real 1x1 PNG (via Pillow), since ImageField validates its content, not just the
    # extension - a hand-crafted byte string is too easy to get subtly wrong (bad CRC, etc.).
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGB', (1, 1)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@pytest.mark.django_db
def test_diagnostic_image_filename_property(step):
    image = TestStepDiagnosticImage.objects.create(step=step, image=_img('u3-location.png'))
    assert image.filename == 'u3-location.png'


@pytest.mark.django_db
def test_add_diagnostic_image(client, staff_user, step):
    client.force_login(staff_user)
    response = client.post(
        reverse('testing:test_step_diagnostic_image_add', args=[step.pk]),
        {'image': _img('u3.png'), 'caption': 'Check U3 for a cold joint'},
    )
    assert response.status_code == 302

    step.refresh_from_db()
    assert step.diagnostic_images.count() == 1
    image = step.diagnostic_images.get()
    assert image.filename == 'u3.png'
    assert image.caption == 'Check U3 for a cold joint'


@pytest.mark.django_db
def test_diagnostic_images_accumulate_in_order(client, staff_user, step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('a.png')})
    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('b.png')})

    step.refresh_from_db()
    assert [i.filename for i in step.diagnostic_images.all()] == ['a.png', 'b.png']


@pytest.mark.django_db
def test_same_filename_on_different_steps_does_not_clash(client, staff_user, suite, step):
    """Unlike TestStepAsset, diagnostic images live under a per-step package folder, so two
    different steps can attach the same filename without any clash check refusing it."""
    other_step = TestStep.objects.create(
        suite=suite, step_type=TestStep.BEEP, name='Beep',
        config={'duration_ms': 100, 'schema_version': 1},
    )
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('shared.png')})
    response = client.post(reverse('testing:test_step_diagnostic_image_add', args=[other_step.pk]), {'image': _img('shared.png')})
    assert response.status_code == 302

    step.refresh_from_db()
    other_step.refresh_from_db()
    assert step.diagnostic_images.count() == 1
    assert other_step.diagnostic_images.count() == 1


@pytest.mark.django_db
def test_delete_diagnostic_image(client, staff_user, step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('u3.png')})
    image = step.diagnostic_images.get()
    path = image.image.path

    response = client.post(reverse('testing:test_step_diagnostic_image_delete', args=[image.pk]))
    assert response.status_code == 302

    step.refresh_from_db()
    assert step.diagnostic_images.count() == 0
    assert not os.path.exists(path)


@pytest.mark.django_db
def test_diagnostic_image_views_require_staff(client, plain_user, step):
    client.force_login(plain_user)
    response = client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('u3.png')})
    assert response.status_code == 302
    assert step.diagnostic_images.count() == 0


@pytest.mark.django_db
def test_adding_a_diagnostic_image_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, step):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('u3.png')})
    assert response.status_code == 302

    step.refresh_from_db()
    assert step.diagnostic_images.count() == 0
    suite.refresh_from_db()
    assert suite.status == TestSuite.SAVED

    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    new_step = draft.steps.get()
    assert new_step.diagnostic_images.get().filename == 'u3.png'


@pytest.mark.django_db
def test_fork_draft_duplicates_diagnostic_image_bytes_independently(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('u3.png')})
    original_image = step.diagnostic_images.get()
    original_path = original_image.image.path

    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])

    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('u3-zoom.png')})

    draft = design.test_suites.first()
    assert draft.version == 2
    assert os.path.exists(original_path)
    original_image.refresh_from_db()
    assert original_image.filename == 'u3.png'


@pytest.mark.django_db
def test_diagnostic_note_saved_via_step_edit(client, staff_user, step):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_step_edit', args=[step.pk]), {
        'step_type': step.step_type,
        'name': step.name,
        'abort_on_fail': False,
        'include_on_docket': True,
        'diagnostic_note': 'Check U3 for a cold solder joint',
        'rail': '5V', 'min_v': '4.8', 'max_v': '5.2',
    })
    assert response.status_code == 302

    step.refresh_from_db()
    assert step.diagnostic_note == 'Check U3 for a cold solder joint'


@pytest.mark.django_db
def test_copy_steps_from_copies_diagnostic_note_and_images(client, staff_user, design, suite, step):
    step.diagnostic_note = 'Check U3'
    step.save(update_fields=['diagnostic_note'])
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('u3.png')})
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])

    org2 = Org.objects.create(company_name='Diagnostic Test Org 2')
    dest_design = Design.objects.create(client=org2, sku='DT2', name='Dest Design', hw_version='1.0')

    response = client.post(reverse('testing:test_suite_copy_steps_from', args=[dest_design.pk]),
                            {'source_design': design.pk})
    assert response.status_code == 302

    dest_step = dest_design.test_suites.first().steps.get()
    assert dest_step.diagnostic_note == 'Check U3'
    assert dest_step.diagnostic_images.get().filename == 'u3.png'
    # The copy is an independent file/row, not a shared reference.
    assert dest_step.diagnostic_images.get().pk != step.diagnostic_images.get().pk


@pytest.mark.django_db
def test_serialize_omits_diagnostic_key_when_empty(client, staff_user, step):
    from testing.views import _serialize_test_suite
    data = _serialize_test_suite(step.suite)
    assert 'diagnostic' not in data['test_steps'][0]


@pytest.mark.django_db
def test_serialize_includes_diagnostic_when_present(client, staff_user, step):
    from testing.views import _serialize_test_suite
    step.diagnostic_note = 'Check U3'
    step.save(update_fields=['diagnostic_note'])
    TestStepDiagnosticImage.objects.create(step=step, image=_img('u3.png'))

    data = _serialize_test_suite(step.suite)
    diagnostic = data['test_steps'][0]['diagnostic']
    assert diagnostic['note'] == 'Check U3'
    assert diagnostic['images'] == [f'diagnostics/{step.pk}/u3.png']


@pytest.mark.django_db
def test_download_bundles_diagnostic_image_under_per_step_folder(client, staff_user, step):
    step.diagnostic_note = 'Check U3'
    step.save(update_fields=['diagnostic_note'])
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_diagnostic_image_add', args=[step.pk]), {'image': _img('u3.png')})

    design = step.suite.design
    response = client.get(reverse('testing:test_suite_download', args=[design.pk]))
    archive = zipfile.ZipFile(io.BytesIO(response.content))

    package_name = f'{slugify(design.sku)}-hw{slugify(design.hw_version)}-test-suite-v{step.suite.version}'
    names = archive.namelist()
    assert f'{package_name}/diagnostics/{step.pk}/u3.png' in names

    definition = json.loads(archive.read(f'{package_name}/test-suite-definition.json'))
    diagnostic = definition['test_steps'][0]['diagnostic']
    assert diagnostic['note'] == 'Check U3'
    assert diagnostic['images'] == [f'diagnostics/{step.pk}/u3.png']
