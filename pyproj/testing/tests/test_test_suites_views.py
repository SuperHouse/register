import json

import pytest
from django.urls import reverse

from crm.models import Org
from device.models import Design
from testing.models import TestStep, TestSuite


@pytest.fixture
def staff_user(django_user_model):
    return django_user_model.objects.create_user(email='suite-staff@example.com', password='staffy', is_staff=True)


@pytest.fixture
def plain_user(django_user_model):
    return django_user_model.objects.create_user(email='suite-plain@example.com', password='plainy')


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Suite View Org')
    return Design.objects.create(client=org, sku='SV1', name='Suite View Design', hw_version='1.0')


@pytest.fixture
def suite(design):
    return TestSuite.objects.create(design=design, version=1)


@pytest.fixture
def step(suite):
    return TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='Settle', config={'delay_ms': 250})


@pytest.mark.django_db
def test_non_staff_users_are_redirected(client, plain_user, design, suite, step):
    urls = [
        reverse('testing:test_suite_current', args=[design.pk]),
        reverse('testing:test_suite_save_new_version', args=[design.pk]),
        reverse('testing:test_suite_version_list', args=[design.pk]),
        reverse('testing:test_suite_version_detail', args=[design.pk, suite.version]),
        reverse('testing:test_step_edit', args=[step.pk]),
        reverse('testing:test_step_delete', args=[step.pk]),
    ]
    client.force_login(plain_user)
    for url in urls:
        response = client.get(url)
        assert response.status_code == 302, url


@pytest.mark.django_db
def test_staff_sees_pages(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    for url in [
        reverse('testing:test_suite_current', args=[design.pk]),
        reverse('testing:test_suite_save_new_version', args=[design.pk]),
        reverse('testing:test_suite_version_list', args=[design.pk]),
        reverse('testing:test_suite_version_detail', args=[design.pk, suite.version]),
        reverse('testing:test_step_edit', args=[step.pk]),
        reverse('testing:test_step_delete', args=[step.pk]),
    ]:
        response = client.get(url)
        assert response.status_code == 200, url


@pytest.mark.django_db
def test_suite_current_lazily_creates_version_one(client, staff_user, design):
    assert design.test_suites.count() == 0
    client.force_login(staff_user)
    response = client.get(reverse('testing:test_suite_current', args=[design.pk]))
    assert response.status_code == 200
    assert design.test_suites.count() == 1
    assert design.test_suites.first().version == 1


@pytest.mark.django_db
def test_suite_current_does_not_duplicate_on_repeat_visits(client, staff_user, design):
    client.force_login(staff_user)
    client.get(reverse('testing:test_suite_current', args=[design.pk]))
    client.get(reverse('testing:test_suite_current', args=[design.pk]))
    assert design.test_suites.count() == 1


@pytest.mark.django_db
def test_step_add_targets_current_suite(client, staff_user, design, suite):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_step_add', args=[design.pk]), {'step_type': TestStep.BEEP})
    assert response.status_code == 302

    new_step = TestStep.objects.get(suite=suite, step_type=TestStep.BEEP)
    assert new_step.name == 'Beep'
    assert response.url == reverse('testing:test_step_edit', args=[new_step.pk])


@pytest.mark.django_db
def test_add_step_dropdown_and_edit_page_type_dropdown_are_alphabetical(client, staff_user, design, suite, step):
    client.force_login(staff_user)

    suite_content = client.get(reverse('testing:test_suite_current', args=[design.pk])).content.decode()
    add_select = suite_content.split('id="id_step_type"')[1].split('</select>')[0]
    labels_in_add_dropdown = [line.split('>')[1] for line in add_select.split('<option value=') if '>' in line][:6]
    assert labels_in_add_dropdown == sorted(labels_in_add_dropdown)

    step_edit_content = client.get(reverse('testing:test_step_edit', args=[step.pk])).content.decode()
    edit_select = step_edit_content.split('id="id_step_type"')[1].split('</select>')[0]
    labels_in_edit_dropdown = [line.split('>')[1] for line in edit_select.split('<option value=') if '>' in line][:6]
    assert labels_in_edit_dropdown == sorted(labels_in_edit_dropdown)


@pytest.mark.django_db
def test_copy_steps_from_appends_to_end_with_config_preserved(client, staff_user, design, suite, step):
    org2 = Org.objects.create(company_name='Source Org')
    source_design = Design.objects.create(client=org2, sku='SRC1', name='Source Design', hw_version='1.0')
    source_suite = TestSuite.objects.create(design=source_design, version=1)
    TestStep.objects.create(
        suite=source_suite, order=1, step_type=TestStep.BEEP, name='Beep Twice',
        hard_fail=True, config={'count': 2, 'duration_ms': 300, 'schema_version': 1},
    )

    client.force_login(staff_user)
    response = client.post(reverse('testing:test_suite_copy_steps_from', args=[design.pk]), {
        'source_design': source_design.pk,
    })
    assert response.status_code == 302
    assert response.url == reverse('testing:test_suite_current', args=[design.pk])

    suite_steps = list(suite.steps.order_by('order'))
    assert len(suite_steps) == 2
    assert suite_steps[0].pk == step.pk  # original step untouched, still first
    copied = suite_steps[1]
    assert copied.step_type == TestStep.BEEP
    assert copied.name == 'Beep Twice'
    assert copied.hard_fail is True
    assert copied.config == {'count': 2, 'duration_ms': 300, 'schema_version': 1}
    assert copied.order == step.order + 1

    # Source is untouched (steps were copied, not moved).
    assert source_suite.steps.count() == 1


@pytest.mark.django_db
def test_copy_steps_from_excludes_self_and_obsolete_designs(client, staff_user, design):
    org2 = Org.objects.create(company_name='Obsolete Org')
    obsolete_design = Design.objects.create(client=org2, sku='OBS1', name='Obsolete Design', hw_version='1.0', obsolete=True)
    org3 = Org.objects.create(company_name='Active Org')
    other_active_design = Design.objects.create(client=org3, sku='ACT1', name='Active Design', hw_version='1.0')

    client.force_login(staff_user)
    content = client.get(reverse('testing:test_suite_current', args=[design.pk])).content.decode()
    select = content.split('id="id_source_design"')[1].split('</select>')[0]

    assert f'value="{design.pk}"' not in select  # can't copy a design's suite onto itself
    assert f'value="{obsolete_design.pk}"' not in select
    assert f'value="{other_active_design.pk}"' in select


@pytest.mark.django_db
def test_copy_steps_from_warns_when_source_has_no_steps(client, staff_user, design):
    org2 = Org.objects.create(company_name='Empty Org')
    empty_design = Design.objects.create(client=org2, sku='EMPTY1', name='Empty Design', hw_version='1.0')

    client.force_login(staff_user)
    response = client.post(reverse('testing:test_suite_copy_steps_from', args=[design.pk]), {
        'source_design': empty_design.pk,
    })
    assert response.status_code == 302
    assert TestStep.objects.filter(suite__design=design).count() == 0


@pytest.mark.django_db
def test_step_edit_updates_config(client, staff_user, step):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_step_edit', args=[step.pk]), {
        'step_type': TestStep.DELAY,
        'name': 'Settle Longer',
        'delay_ms': '1000',
    })
    assert response.status_code == 302
    step.refresh_from_db()
    assert step.name == 'Settle Longer'
    assert step.config['delay_ms'] == 1000


@pytest.mark.django_db
def test_step_delete(client, staff_user, suite, step):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_step_delete', args=[step.pk]))
    assert response.status_code == 302
    assert not TestStep.objects.filter(pk=step.pk).exists()


@pytest.mark.django_db
def test_step_reorder(client, staff_user, design, suite):
    step_a = TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='A', order=1)
    step_b = TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='B', order=2)
    client.force_login(staff_user)

    response = client.post(
        reverse('testing:test_step_reorder', args=[design.pk]),
        data=json.dumps({'order': [step_b.pk, step_a.pk]}),
        content_type='application/json',
    )
    assert response.status_code == 200
    step_a.refresh_from_db()
    step_b.refresh_from_db()
    assert step_b.order == 1
    assert step_a.order == 2


@pytest.mark.django_db
def test_save_new_version_freezes_current_and_copies_steps_forward(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {
        'notes': 'First production release',
    })
    assert response.status_code == 302
    assert response.url == reverse('testing:test_suite_current', args=[design.pk])

    suite.refresh_from_db()
    assert suite.notes == 'First production release'

    assert design.test_suites.count() == 2
    new_suite = design.test_suites.first()  # highest version = current
    assert new_suite.version == 2
    assert new_suite.pk != suite.pk

    # The new version's steps are independent copies, not the same rows.
    assert list(new_suite.steps.values_list('step_type', 'name', 'config')) == \
        list(suite.steps.values_list('step_type', 'name', 'config'))
    assert new_suite.steps.first().pk != step.pk


@pytest.mark.django_db
def test_editing_or_deleting_a_step_on_a_historical_version_is_blocked(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    # Freeze v1 (with `step` on it) and move to v2.
    client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {'notes': ''})
    suite.refresh_from_db()
    assert design.test_suites.first().version == 2  # v1 (`suite`/`step`) is now historical

    edit_response = client.post(reverse('testing:test_step_edit', args=[step.pk]), {
        'step_type': TestStep.DELAY, 'name': 'Should not apply', 'delay_ms': '1',
    })
    assert edit_response.status_code == 302
    assert edit_response.url == reverse('testing:test_suite_version_detail', args=[design.pk, suite.version])
    step.refresh_from_db()
    assert step.name == 'Settle'  # unchanged

    delete_response = client.post(reverse('testing:test_step_delete', args=[step.pk]))
    assert delete_response.status_code == 302
    assert TestStep.objects.filter(pk=step.pk).exists()  # not deleted


@pytest.mark.django_db
def test_version_list_shows_all_versions(client, staff_user, design, suite):
    client.force_login(staff_user)
    client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {'notes': ''})

    content = client.get(reverse('testing:test_suite_version_list', args=[design.pk])).content.decode()
    assert 'v1' in content
    assert 'v2' in content


@pytest.mark.django_db
def test_version_detail_shows_read_only_steps(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    content = client.get(reverse('testing:test_suite_version_detail', args=[design.pk, suite.version])).content.decode()
    assert 'Settle' in content
    assert 'Delay' in content
