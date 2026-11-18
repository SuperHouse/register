"""Batches list ordering by effective due date (register#157)."""
from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from crm.models import Org
from device.models import Design
from erp.models import AssemblyCostSettings, Batch, BatchProductionStage, ProductionStage


def _created(y, m, d):
    return timezone.make_aware(datetime(y, m, d, 9, 0))


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Sorting Org')
    return Design.objects.create(client=org, sku='SORT1', name='Sort Design', hw_version='1.0')


@pytest.mark.django_db
def test_implied_due_date_uses_lead_time(design):
    batch = Batch.objects.create(design=design, quantity=1, created_dt=_created(2026, 11, 1))
    assert batch.implied_due_date(21) == date(2026, 11, 22)
    assert batch.effective_due_date(21) == date(2026, 11, 22)
    assert batch.effective_due_date(7) == date(2026, 11, 8)

    batch.due_date = date(2026, 12, 25)
    assert batch.effective_due_date(21) == date(2026, 12, 25)


@pytest.mark.django_db
def test_batch_list_interleaves_dated_and_undated(client, django_user_model, design):
    assert AssemblyCostSettings.get_solo().typical_assembly_days == 21  # the default
    # Effective due dates: old_undated 22-Oct, dated_soon 1-Nov, new_undated 30-Nov, dated_late 1-Dec.
    old_undated = Batch.objects.create(design=design, quantity=1, po='OLD-UNDATED',
                                       created_dt=_created(2026, 10, 1))
    dated_late = Batch.objects.create(design=design, quantity=1, po='DATED-LATE',
                                      created_dt=_created(2026, 10, 5), due_date=date(2026, 12, 1))
    new_undated = Batch.objects.create(design=design, quantity=1, po='NEW-UNDATED',
                                       created_dt=_created(2026, 11, 9))
    dated_soon = Batch.objects.create(design=design, quantity=1, po='DATED-SOON',
                                      created_dt=_created(2026, 11, 10), due_date=date(2026, 11, 1))

    staff = django_user_model.objects.create_user(email='sortstaff@example.com', password='x', is_staff=True)
    client.force_login(staff)
    response = client.get(reverse('erp:batch_list'))

    new_group = dict((cat, group) for _, cat, group in response.context['batch_groups'])['new']
    # Most urgent at the bottom of the group.
    assert new_group == [dated_late, new_undated, dated_soon, old_undated]
    # The implied date is shown for undated batches; a real date shows without the "~".
    content = response.content.decode()
    assert '~22-Oct-2026' in content
    assert '~1-Dec-2026' not in content


@pytest.mark.django_db
def test_complete_group_keeps_newest_first(client, django_user_model, design):
    stage_type = ProductionStage.objects.create(name='Sort Done Stage')
    older = Batch.objects.create(design=design, quantity=1, created_dt=_created(2026, 10, 1),
                                 due_date=date(2026, 10, 2))
    newer = Batch.objects.create(design=design, quantity=1, created_dt=_created(2026, 11, 1),
                                 due_date=date(2026, 12, 31))
    for batch in (older, newer):
        BatchProductionStage.objects.create(batch=batch, production_stage=stage_type,
                                            status=BatchProductionStage.DONE)

    staff = django_user_model.objects.create_user(email='sortstaff2@example.com', password='x', is_staff=True)
    client.force_login(staff)
    response = client.get(reverse('erp:batch_list'))

    complete = dict((cat, group) for _, cat, group in response.context['batch_groups'])['complete']
    assert complete == [newer, older]


@pytest.mark.django_db
def test_batch_list_uses_typical_assembly_days_setting(client, django_user_model, design):
    """Changing the setting changes the order: with a 7-day lead time the undated batch
    (created 1-Nov, implied 8-Nov) becomes more urgent than one due 15-Nov, so it moves to the bottom."""
    dated = Batch.objects.create(design=design, quantity=1, created_dt=_created(2026, 10, 1),
                                 due_date=date(2026, 11, 15))
    undated = Batch.objects.create(design=design, quantity=1, created_dt=_created(2026, 11, 1))
    staff = django_user_model.objects.create_user(email='sortstaff3@example.com', password='x', is_staff=True)
    client.force_login(staff)

    def new_group():
        response = client.get(reverse('erp:batch_list'))
        return dict((cat, group) for _, cat, group in response.context['batch_groups'])['new']

    assert new_group() == [undated, dated]  # default 21 days: undated is implied 22-Nov
    AssemblyCostSettings.objects.filter(pk=1).update(typical_assembly_days=7)
    assert new_group() == [dated, undated]


@pytest.mark.django_db
def test_assembly_settings_page_edits_typical_assembly_days(client, django_user_model):
    staff = django_user_model.objects.create_user(email='sortstaff4@example.com', password='x', is_staff=True)
    client.force_login(staff)
    url = reverse('erp:assembly_cost_settings_edit')
    response = client.get(url)
    assert 'Typical assembly time (days)' in response.content.decode()

    data = {name: '0' for name in (
        'smt_joint_cost_cents', 'pth_joint_cost_cents', 'consigned_smt_joint_cost_cents',
        'consigned_pth_joint_cost_cents', 'labour_rate', 'kitting_margin_percent',
        'conformal_coating_charge', 'anti_shock_glue_charge',
    )}
    data['typical_assembly_days'] = '10'
    response = client.post(url, data)
    assert response.status_code == 302
    assert AssemblyCostSettings.get_solo().typical_assembly_days == 10


@pytest.mark.django_db
def test_batch_list_marks_overdue_block(client, django_user_model, design):
    """Past-due batches (real or implied date before today) form the bottom block of a group,
    with a red line on the first of them; a batch due today isn't overdue."""
    today = timezone.localdate()
    now = timezone.now()
    later = Batch.objects.create(design=design, quantity=1, po='DUE-LATER', created_dt=now,
                                 due_date=today + timedelta(days=5))
    due_today = Batch.objects.create(design=design, quantity=1, po='DUE-TODAY', created_dt=now,
                                     due_date=today)
    late = Batch.objects.create(design=design, quantity=1, po='LATE', created_dt=now,
                                due_date=today - timedelta(days=2))
    implied_late = Batch.objects.create(design=design, quantity=1, po='IMPLIED-LATE',
                                        created_dt=now - timedelta(days=60))

    staff = django_user_model.objects.create_user(email='sortstaff5@example.com', password='x', is_staff=True)
    client.force_login(staff)
    response = client.get(reverse('erp:batch_list'))

    new_group = dict((cat, group) for _, cat, group in response.context['batch_groups'])['new']
    assert new_group == [later, due_today, late, implied_late]
    assert [b.overdue for b in new_group] == [False, False, True, True]
    assert [getattr(b, 'first_overdue', False) for b in new_group] == [False, False, True, False]

    content = response.content.decode()
    assert content.count('<tr class="first-overdue"') == 1
    assert content.index('DUE-TODAY') < content.index('<tr class="first-overdue"') < content.index('>LATE<')


@pytest.mark.django_db
def test_batch_list_no_divider_when_nothing_overdue(client, django_user_model, design):
    Batch.objects.create(design=design, quantity=1, due_date=timezone.localdate() + timedelta(days=3))
    staff = django_user_model.objects.create_user(email='sortstaff6@example.com', password='x', is_staff=True)
    client.force_login(staff)
    response = client.get(reverse('erp:batch_list'))
    assert '<tr class="first-overdue"' not in response.content.decode()
