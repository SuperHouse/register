import json

import pytest
from django.urls import reverse

from crm.models import Org
from device.models import Design
from testing.models import ManualCheck, TestStep, TestSuite


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
    """A draft suite - the shape most tests want, since it's directly editable without
    triggering the fork-on-write behaviour covered separately below (issue #110)."""
    return TestSuite.objects.create(design=design, version=1, status=TestSuite.DRAFT)


@pytest.fixture
def step(suite):
    return TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='Settle', config={'delay_ms': 250})


@pytest.fixture
def check(suite):
    return ManualCheck.objects.create(suite=suite, text='Confirm LED lights up', order=1)


@pytest.mark.django_db
def test_non_staff_users_are_redirected(client, plain_user, design, suite, step, check):
    urls = [
        reverse('testing:test_suite_save_new_version', args=[design.pk]),
        reverse('testing:test_suite_discard_draft', args=[design.pk]),
        reverse('testing:test_suite_version_list', args=[design.pk]),
        reverse('testing:test_suite_version_detail', args=[design.pk, suite.version]),
        reverse('testing:test_step_edit', args=[step.pk]),
        reverse('testing:test_step_delete', args=[step.pk]),
        reverse('testing:manual_check_edit', args=[check.pk]),
        reverse('testing:manual_check_delete', args=[check.pk]),
    ]
    client.force_login(plain_user)
    for url in urls:
        response = client.get(url)
        assert response.status_code == 302, url


@pytest.mark.django_db
def test_staff_sees_pages(client, staff_user, design, suite, step, check):
    client.force_login(staff_user)
    for url in [
        reverse('testing:test_suite_save_new_version', args=[design.pk]),
        reverse('testing:test_suite_discard_draft', args=[design.pk]),
        reverse('testing:test_suite_version_list', args=[design.pk]),
        reverse('testing:test_suite_version_detail', args=[design.pk, suite.version]),
        reverse('testing:test_step_edit', args=[step.pk]),
        reverse('testing:test_step_delete', args=[step.pk]),
        reverse('testing:manual_check_edit', args=[check.pk]),
        reverse('testing:manual_check_delete', args=[check.pk]),
    ]:
        response = client.get(url)
        assert response.status_code == 200, url


@pytest.mark.django_db
def test_design_detail_does_not_create_suite_just_from_viewing(client, staff_user, design):
    """The Test Suite tab (issue #102) lives on the Design detail page now, but merely
    viewing that page must not itself create a TestSuite row - only actually adding a step
    (test_step_add) does, lazily. Otherwise every visit to every design's page would create
    an empty TestSuite for it."""
    assert design.test_suites.count() == 0
    client.force_login(staff_user)
    response = client.get(reverse('design_detail', args=[design.pk]))
    assert response.status_code == 200
    assert design.test_suites.count() == 0


@pytest.mark.django_db
def test_step_add_lazily_creates_version_one_when_none_exists(client, staff_user, design):
    assert design.test_suites.count() == 0
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_step_add', args=[design.pk]), {'step_type': TestStep.DELAY})
    assert response.status_code == 302
    assert design.test_suites.count() == 1
    assert design.test_suites.first().version == 1


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

    design_content = client.get(reverse('design_detail', args=[design.pk])).content.decode()
    add_select = design_content.split('id="id_step_type"')[1].split('</select>')[0]
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
    assert response.url == reverse('design_detail', args=[design.pk]) + '#test-suite'

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
    content = client.get(reverse('design_detail', args=[design.pk])).content.decode()
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
def test_save_new_version_promotes_draft_in_place(client, staff_user, design, suite, step):
    """Issue #110: saving no longer copies the draft to a new row - it just flips the draft's
    own status to SAVED, so the version number keeps meaning exactly one thing."""
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {
        'notes': 'First production release',
    })
    assert response.status_code == 302
    assert response.url == reverse('design_detail', args=[design.pk]) + '#test-suite'

    suite.refresh_from_db()
    assert suite.notes == 'First production release'
    assert suite.status == TestSuite.SAVED

    assert design.test_suites.count() == 1
    assert design.test_suites.first().pk == suite.pk
    assert design.test_suites.first().version == 1


@pytest.mark.django_db
def test_save_new_version_with_no_draft_is_a_noop(client, staff_user, design, suite):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {'notes': 'x'})
    assert response.status_code == 302
    assert design.test_suites.count() == 1
    suite.refresh_from_db()
    assert suite.notes != 'x'


@pytest.mark.django_db
def test_editing_or_deleting_a_step_on_a_historical_version_is_blocked(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    # Save v1 (with `step` on it), then make a further edit - this forks v2, leaving v1
    # genuinely historical (as opposed to merely SAVED-but-still-current).
    client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {'notes': ''})
    client.post(reverse('testing:test_step_add', args=[design.pk]), {'step_type': TestStep.BEEP})
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
def test_editing_a_step_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, step):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_step_edit', args=[step.pk]), {
        'step_type': TestStep.DELAY, 'name': 'Settle Longer', 'delay_ms': '1000',
    })
    assert response.status_code == 302

    # The original SAVED step/suite are untouched.
    step.refresh_from_db()
    assert step.name == 'Settle'
    suite.refresh_from_db()
    assert suite.status == TestSuite.SAVED

    # A new draft was forked, with the edit applied to its copy of the step.
    assert design.test_suites.count() == 2
    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    new_step = draft.steps.get()
    assert new_step.pk != step.pk
    assert new_step.name == 'Settle Longer'
    assert new_step.config['delay_ms'] == 1000


@pytest.mark.django_db
def test_deleting_a_step_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, step):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_step_delete', args=[step.pk]))
    assert response.status_code == 302

    assert TestStep.objects.filter(pk=step.pk).exists()  # the original SAVED step is untouched

    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    assert draft.steps.count() == 0  # the copy was deleted


@pytest.mark.django_db
def test_adding_a_step_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, step):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_step_add', args=[design.pk]), {'step_type': TestStep.BEEP})
    assert response.status_code == 302

    assert design.test_suites.count() == 2
    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    # The draft has both the copied original step and the newly-added one.
    assert list(draft.steps.order_by('order').values_list('step_type', flat=True)) == [TestStep.DELAY, TestStep.BEEP]

    suite.refresh_from_db()
    assert suite.steps.count() == 1  # the SAVED version is untouched


@pytest.mark.django_db
def test_reordering_steps_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite):
    step_a = TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='A', order=1)
    step_b = TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='B', order=2)
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    # The payload carries the *pre-fork* pks, exactly as the page would have rendered them.
    response = client.post(
        reverse('testing:test_step_reorder', args=[design.pk]),
        data=json.dumps({'order': [step_b.pk, step_a.pk]}),
        content_type='application/json',
    )
    assert response.status_code == 200

    step_a.refresh_from_db()
    step_b.refresh_from_db()
    assert step_a.order == 1 and step_b.order == 2  # originals untouched

    draft = design.test_suites.first()
    assert draft.status == TestSuite.DRAFT
    assert draft.steps.get(name='B').order == 1
    assert draft.steps.get(name='A').order == 2


@pytest.mark.django_db
def test_invalid_step_edit_does_not_fork_a_draft(client, staff_user, design, suite, step):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_step_edit', args=[step.pk]), {
        'step_type': TestStep.DELAY, 'name': 'Bad', 'delay_ms': '',  # delay_ms is required
    })
    assert response.status_code == 200  # re-renders the form with errors, no redirect
    assert design.test_suites.count() == 1  # nothing forked for a rejected submission


@pytest.mark.django_db
def test_viewing_edit_page_for_a_saved_step_does_not_fork(client, staff_user, design, suite, step):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.get(reverse('testing:test_step_edit', args=[step.pk]))
    assert response.status_code == 200
    assert design.test_suites.count() == 1  # merely viewing doesn't fork


@pytest.mark.django_db
def test_discard_draft(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    response = client.post(reverse('testing:test_suite_discard_draft', args=[design.pk]))
    assert response.status_code == 302
    assert not TestSuite.objects.filter(pk=suite.pk).exists()
    assert not TestStep.objects.filter(pk=step.pk).exists()


@pytest.mark.django_db
def test_discard_draft_with_no_draft_is_a_noop(client, staff_user, design, suite):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_suite_discard_draft', args=[design.pk]))
    assert response.status_code == 302
    assert TestSuite.objects.filter(pk=suite.pk).exists()


@pytest.mark.django_db
def test_copy_steps_from_uses_source_saved_version_not_its_draft(client, staff_user, design):
    org2 = Org.objects.create(company_name='Source Org 2')
    source_design = Design.objects.create(client=org2, sku='SRC2', name='Source Design 2', hw_version='1.0')
    saved_suite = TestSuite.objects.create(design=source_design, version=1, status=TestSuite.SAVED)
    TestStep.objects.create(suite=saved_suite, order=1, step_type=TestStep.DELAY, name='Saved Step', config={'delay_ms': 5})
    draft_suite = TestSuite.objects.create(design=source_design, version=2, status=TestSuite.DRAFT)
    TestStep.objects.create(suite=draft_suite, order=1, step_type=TestStep.DELAY, name='Draft Step', config={'delay_ms': 5})

    client.force_login(staff_user)
    client.post(reverse('testing:test_suite_copy_steps_from', args=[design.pk]), {'source_design': source_design.pk})

    copied_names = list(TestStep.objects.filter(suite__design=design).values_list('name', flat=True))
    assert copied_names == ['Saved Step']


@pytest.mark.django_db
def test_version_list_shows_all_versions(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {'notes': ''})
    client.post(reverse('testing:test_step_add', args=[design.pk]), {'step_type': TestStep.BEEP})  # forks v2

    content = client.get(reverse('testing:test_suite_version_list', args=[design.pk])).content.decode()
    assert '>v1<' in content
    assert '>v2<' in content


@pytest.mark.django_db
def test_version_detail_shows_read_only_steps(client, staff_user, design, suite, step):
    client.force_login(staff_user)
    content = client.get(reverse('testing:test_suite_version_detail', args=[design.pk, suite.version])).content.decode()
    assert 'Settle' in content
    assert 'Delay' in content


@pytest.mark.django_db
def test_version_detail_for_saved_version_superseded_by_newer_draft(client, staff_user, design, suite, step):
    """A version can be simultaneously "Current" (the latest saved one - what a Tester would
    fetch) and no longer directly editable (because a newer draft has since forked off it).
    That's a different situation from a version superseded by another *saved* version, and
    must not be mislabelled "Historical" just because it's not the highest row any more."""
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)
    client.post(reverse('testing:test_step_add', args=[design.pk]), {'step_type': TestStep.BEEP})  # forks v2

    content = client.get(reverse('testing:test_suite_version_detail', args=[design.pk, suite.version])).content.decode()
    assert 'Current' in content
    assert 'Historical' not in content
    assert 'newer draft' in content
    assert '(v2)' in content
    assert 'frozen historical record' not in content


# --- Manual Checks (issue #112) ---

@pytest.mark.django_db
def test_manual_check_add_lazily_creates_a_draft_when_none_exists(client, staff_user, design):
    assert design.test_suites.count() == 0
    client.force_login(staff_user)
    response = client.post(reverse('testing:manual_check_add', args=[design.pk]), {'text': 'Confirm LED lights up'})
    assert response.status_code == 302
    assert design.test_suites.count() == 1
    suite = design.test_suites.first()
    assert suite.version == 1
    assert suite.status == TestSuite.DRAFT
    assert suite.manual_checks.get().text == 'Confirm LED lights up'


@pytest.mark.django_db
def test_manual_check_add_targets_the_draft_suite(client, staff_user, design, suite, check):
    client.force_login(staff_user)
    response = client.post(reverse('testing:manual_check_add', args=[design.pk]), {'text': 'Second check'})
    assert response.status_code == 302

    new_check = ManualCheck.objects.get(suite=suite, text='Second check')
    assert new_check.order == check.order + 1


@pytest.mark.django_db
def test_manual_check_add_rejects_blank_text(client, staff_user, design):
    client.force_login(staff_user)
    response = client.post(reverse('testing:manual_check_add', args=[design.pk]), {'text': ''})
    assert response.status_code == 302
    assert design.test_suites.count() == 0  # nothing was created


@pytest.mark.django_db
def test_manual_check_edit_updates_text(client, staff_user, check):
    client.force_login(staff_user)
    response = client.post(reverse('testing:manual_check_edit', args=[check.pk]), {'text': 'Updated text'})
    assert response.status_code == 302
    check.refresh_from_db()
    assert check.text == 'Updated text'


@pytest.mark.django_db
def test_manual_check_delete(client, staff_user, check):
    client.force_login(staff_user)
    response = client.post(reverse('testing:manual_check_delete', args=[check.pk]))
    assert response.status_code == 302
    assert not ManualCheck.objects.filter(pk=check.pk).exists()


@pytest.mark.django_db
def test_manual_check_reorder(client, staff_user, design, suite):
    check_a = ManualCheck.objects.create(suite=suite, text='A', order=1)
    check_b = ManualCheck.objects.create(suite=suite, text='B', order=2)
    client.force_login(staff_user)

    response = client.post(
        reverse('testing:manual_check_reorder', args=[design.pk]),
        data=json.dumps({'order': [check_b.pk, check_a.pk]}),
        content_type='application/json',
    )
    assert response.status_code == 200
    check_a.refresh_from_db()
    check_b.refresh_from_db()
    assert check_b.order == 1
    assert check_a.order == 2


@pytest.mark.django_db
def test_editing_a_manual_check_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, check):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:manual_check_edit', args=[check.pk]), {'text': 'Changed'})
    assert response.status_code == 302

    check.refresh_from_db()
    assert check.text == 'Confirm LED lights up'  # original SAVED check untouched
    suite.refresh_from_db()
    assert suite.status == TestSuite.SAVED

    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    new_check = draft.manual_checks.get()
    assert new_check.pk != check.pk
    assert new_check.text == 'Changed'


@pytest.mark.django_db
def test_deleting_a_manual_check_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, check):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:manual_check_delete', args=[check.pk]))
    assert response.status_code == 302

    assert ManualCheck.objects.filter(pk=check.pk).exists()  # original SAVED check untouched

    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    assert draft.manual_checks.count() == 0  # the copy was deleted


@pytest.mark.django_db
def test_adding_a_manual_check_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, check):
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(reverse('testing:manual_check_add', args=[design.pk]), {'text': 'New check'})
    assert response.status_code == 302

    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    assert list(draft.manual_checks.order_by('order').values_list('text', flat=True)) == \
        ['Confirm LED lights up', 'New check']

    suite.refresh_from_db()
    assert suite.manual_checks.count() == 1  # the SAVED version is untouched


@pytest.mark.django_db
def test_reordering_manual_checks_on_the_saved_current_version_forks_a_new_draft(client, staff_user, design, suite, check):
    check_b = ManualCheck.objects.create(suite=suite, text='B', order=2)
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    response = client.post(
        reverse('testing:manual_check_reorder', args=[design.pk]),
        data=json.dumps({'order': [check_b.pk, check.pk]}),
        content_type='application/json',
    )
    assert response.status_code == 200

    check.refresh_from_db()
    check_b.refresh_from_db()
    assert check.order == 1 and check_b.order == 2  # originals untouched

    draft = design.test_suites.first()
    assert draft.status == TestSuite.DRAFT
    assert draft.manual_checks.get(text='B').order == 1
    assert draft.manual_checks.get(text='Confirm LED lights up').order == 2


@pytest.mark.django_db
def test_editing_or_deleting_a_manual_check_on_a_historical_version_is_blocked(client, staff_user, design, suite, check):
    client.force_login(staff_user)
    # Save v1 (with `check` on it), then make a further edit - this forks v2, leaving v1
    # genuinely historical.
    client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {'notes': ''})
    client.post(reverse('testing:manual_check_add', args=[design.pk]), {'text': 'Another'})
    assert design.test_suites.first().version == 2

    edit_response = client.post(reverse('testing:manual_check_edit', args=[check.pk]), {'text': 'Should not apply'})
    assert edit_response.status_code == 302
    assert edit_response.url == reverse('testing:test_suite_version_detail', args=[design.pk, suite.version])
    check.refresh_from_db()
    assert check.text == 'Confirm LED lights up'  # unchanged

    delete_response = client.post(reverse('testing:manual_check_delete', args=[check.pk]))
    assert delete_response.status_code == 302
    assert ManualCheck.objects.filter(pk=check.pk).exists()  # not deleted


@pytest.mark.django_db
def test_forking_a_draft_carries_both_steps_and_manual_checks_together(client, staff_user, design, suite, step, check):
    """The core of issue #112: versioning encompasses both lists together, so editing either
    one forks a draft that includes an unchanged copy of the other."""
    suite.status = TestSuite.SAVED
    suite.save(update_fields=['status'])
    client.force_login(staff_user)

    # Editing only the manual check should still carry the step forward into the new draft.
    client.post(reverse('testing:manual_check_edit', args=[check.pk]), {'text': 'Changed'})

    draft = design.test_suites.first()
    assert draft.version == 2
    assert draft.status == TestSuite.DRAFT
    assert draft.steps.get().name == step.name
    assert draft.manual_checks.get().text == 'Changed'


@pytest.mark.django_db
def test_save_new_version_and_discard_draft_apply_to_manual_checks_too(client, staff_user, design, suite, check):
    client.force_login(staff_user)

    response = client.post(reverse('testing:test_suite_save_new_version', args=[design.pk]), {'notes': ''})
    assert response.status_code == 302
    suite.refresh_from_db()
    assert suite.status == TestSuite.SAVED
    assert design.test_suites.count() == 1  # promoted in place, no new row

    # A further edit forks a new draft...
    client.post(reverse('testing:manual_check_add', args=[design.pk]), {'text': 'Another'})
    assert design.test_suites.count() == 2

    # ...which discarding removes entirely, taking its manual checks with it.
    response = client.post(reverse('testing:test_suite_discard_draft', args=[design.pk]))
    assert response.status_code == 302
    assert design.test_suites.count() == 1
    assert ManualCheck.objects.filter(text='Another').count() == 0


@pytest.mark.django_db
def test_copy_steps_from_also_copies_manual_checks(client, staff_user, design):
    org2 = Org.objects.create(company_name='Source Org 3')
    source_design = Design.objects.create(client=org2, sku='SRC3', name='Source Design 3', hw_version='1.0')
    source_suite = TestSuite.objects.create(design=source_design, version=1, status=TestSuite.SAVED)
    ManualCheck.objects.create(suite=source_suite, order=1, text='Check the fuse')

    client.force_login(staff_user)
    client.post(reverse('testing:test_suite_copy_steps_from', args=[design.pk]), {'source_design': source_design.pk})

    copied = ManualCheck.objects.filter(suite__design=design)
    assert copied.count() == 1
    assert copied.get().text == 'Check the fuse'
