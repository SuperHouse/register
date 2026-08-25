import pytest
from django.db import IntegrityError

from crm.models import Org
from device.models import Design
from testing.forms import TestStepForm
from testing.models import TestStep, TestSuite


@pytest.fixture
def design():
    org = Org.objects.create(company_name='Suite Test Org')
    return Design.objects.create(client=org, sku='ST1', name='Suite Test Design', hw_version='1.0')


@pytest.mark.django_db
def test_suite_str(design):
    suite = TestSuite.objects.create(design=design, version=1)
    assert str(suite) == f'{design} Test Suite v1'


@pytest.mark.django_db
def test_suite_unique_version_per_design(design):
    TestSuite.objects.create(design=design, version=1)
    with pytest.raises(IntegrityError):
        TestSuite.objects.create(design=design, version=1)


@pytest.mark.django_db
def test_suite_same_version_allowed_on_different_design(design):
    org2 = Org.objects.create(company_name='Suite Test Org 2')
    other_design = Design.objects.create(client=org2, sku='ST2', name='Other Design', hw_version='1.0')
    TestSuite.objects.create(design=design, version=1)
    TestSuite.objects.create(design=other_design, version=1)  # should not raise
    assert TestSuite.objects.count() == 2


@pytest.mark.django_db
def test_suite_ordering_puts_highest_version_first(design):
    TestSuite.objects.create(design=design, version=1)
    TestSuite.objects.create(design=design, version=3)
    TestSuite.objects.create(design=design, version=2)
    assert [s.version for s in design.test_suites.all()] == [3, 2, 1]


@pytest.mark.django_db
def test_step_str_and_color(design):
    suite = TestSuite.objects.create(design=design, version=1)
    step = TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='Settle', config={'delay_ms': 500})
    assert str(step) == 'Delay: Settle'
    assert step.get_color() == TestStep.STEP_TYPE_COLORS[TestStep.DELAY]


@pytest.mark.django_db
def test_step_config_summary_per_type(design):
    suite = TestSuite.objects.create(design=design, version=1)

    delay = TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='Settle', config={'delay_ms': 250})
    assert delay.get_config_summary() == '250 ms'

    beep = TestStep.objects.create(suite=suite, step_type=TestStep.BEEP, name='Beep', config={'duration_ms': 100})
    assert beep.get_config_summary() == '1 × 100 ms'  # count defaults to 1 when absent from config

    rail_v = TestStep.objects.create(
        suite=suite, step_type=TestStep.READ_RAIL_VOLTAGE, name='Check 5V',
        config={'rail': '5V', 'min_v': 4.8, 'max_v': 5.2},
    )
    assert rail_v.get_config_summary() == '5V: 4.8–5.2 V'


@pytest.mark.django_db
def test_steps_ordered_by_order(design):
    suite = TestSuite.objects.create(design=design, version=1)
    TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='Second', order=2)
    TestStep.objects.create(suite=suite, step_type=TestStep.DELAY, name='First', order=1)
    assert [s.name for s in suite.steps.all()] == ['First', 'Second']


@pytest.mark.django_db
def test_step_form_stamps_schema_version_and_picks_type_fields(design):
    suite = TestSuite.objects.create(design=design, version=1)
    form = TestStepForm(data={'step_type': TestStep.DELAY, 'name': 'Settle', 'delay_ms': '500'})
    assert form.is_valid(), form.errors

    step = form.save(commit=False)
    step.suite = suite
    step.save()

    assert step.config == {'delay_ms': 500, 'schema_version': TestStep.CONFIG_SCHEMA_VERSION}


@pytest.mark.django_db
def test_step_form_requires_type_specific_fields():
    form = TestStepForm(data={'step_type': TestStep.DELAY, 'name': 'Settle'})  # delay_ms deliberately omitted
    assert not form.is_valid()
    assert 'delay_ms' in form.errors


@pytest.mark.django_db
def test_step_form_beep_optional_count_omitted_when_blank():
    form = TestStepForm(data={'step_type': TestStep.BEEP, 'name': 'Beep', 'duration_ms': '100'})  # count blank
    assert form.is_valid(), form.errors
    assert 'count' not in form.cleaned_data['config']
    assert form.cleaned_data['config']['duration_ms'] == 100


def test_step_type_choices_alphabetical_is_sorted_by_label():
    labels = [label for _, label in TestStep.STEP_TYPE_CHOICES_ALPHABETICAL]
    assert labels == sorted(labels)
    # Same set of types as the canonical (definition-order) choices, just reordered.
    assert set(TestStep.STEP_TYPE_CHOICES_ALPHABETICAL) == set(TestStep.STEP_TYPE_CHOICES)


@pytest.mark.django_db
def test_step_form_edit_seeds_initial_from_config_excluding_schema_version(design):
    suite = TestSuite.objects.create(design=design, version=1)
    step = TestStep.objects.create(
        suite=suite, step_type=TestStep.DELAY, name='Settle',
        config={'delay_ms': 500, 'schema_version': 1},
    )
    form = TestStepForm(instance=step)
    assert form.initial['delay_ms'] == 500
    assert 'schema_version' not in form.initial
