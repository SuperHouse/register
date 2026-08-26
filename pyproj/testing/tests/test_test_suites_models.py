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

    py = TestStep.objects.create(
        suite=suite, step_type=TestStep.PYTHON, name='Script',
        config={'python_code': 'print("hello")'},
    )
    assert py.get_config_summary() == 'print("hello")'

    analog_read = TestStep.objects.create(
        suite=suite, step_type=TestStep.IOMOD_ANALOG_READ, name='Check A0',
        config={'iomod': 'A', 'pin': '0', 'expect_min': 10, 'expect_max': 50},
    )
    assert analog_read.get_config_summary() == 'IOMOD A Pin 0: expect 10–50'

    digital_read = TestStep.objects.create(
        suite=suite, step_type=TestStep.IOMOD_DIGITAL_READ, name='Check B3',
        config={'iomod': 'B', 'pin': '3', 'expect': '1'},
    )
    assert digital_read.get_config_summary() == 'IOMOD B Pin 3: expect 1'

    digital_write = TestStep.objects.create(
        suite=suite, step_type=TestStep.IOMOD_DIGITAL_WRITE, name='Set C4',
        config={'iomod': 'C', 'pin': '4', 'digital_write': '0'},
    )
    assert digital_write.get_config_summary() == 'IOMOD C Pin 4: write 0'

    analog_write = TestStep.objects.create(
        suite=suite, step_type=TestStep.IOMOD_ANALOG_WRITE, name='Set D5',
        config={'iomod': 'D', 'pin': '5', 'analog_write': 200},
    )
    assert analog_write.get_config_summary() == 'IOMOD D Pin 5: write 200'


@pytest.mark.django_db
def test_step_config_summary_range_with_only_one_bound(design):
    suite = TestSuite.objects.create(design=design, version=1)
    min_only = TestStep.objects.create(
        suite=suite, step_type=TestStep.IOMOD_ANALOG_READ, name='Min only',
        config={'iomod': 'A', 'pin': '0', 'expect_min': 10},
    )
    assert min_only.get_config_summary() == 'IOMOD A Pin 0: expect ≥10'

    max_only = TestStep.objects.create(
        suite=suite, step_type=TestStep.IOMOD_ANALOG_READ, name='Max only',
        config={'iomod': 'A', 'pin': '0', 'expect_max': 50},
    )
    assert max_only.get_config_summary() == 'IOMOD A Pin 0: expect ≤50'

    neither = TestStep.objects.create(
        suite=suite, step_type=TestStep.IOMOD_ANALOG_READ, name='Neither',
        config={'iomod': 'A', 'pin': '0'},
    )
    assert neither.get_config_summary() == 'IOMOD A Pin 0: expect any'


@pytest.mark.django_db
def test_step_config_summary_python_truncates_and_counts_extra_lines(design):
    suite = TestSuite.objects.create(design=design, version=1)
    code = ('x' * 80) + '\nsecond line\nthird line'
    step = TestStep.objects.create(suite=suite, step_type=TestStep.PYTHON, name='Long script', config={'python_code': code})
    summary = step.get_config_summary()
    assert summary.startswith('x' * 57 + '...')
    assert summary.endswith('(+2 more lines)')


@pytest.mark.django_db
def test_step_config_summary_led_spectral_reading(design):
    suite = TestSuite.objects.create(design=design, version=1)
    with_mux = TestStep.objects.create(
        suite=suite, step_type=TestStep.LED_SPECTRAL_READING, name='Read LED',
        config={
            'mux_addr': '0x70', 'mux_chan': '2', 'i2c_addr': '0x29',
            'r_min': 1, 'r_max': 2, 'g_min': 3, 'g_max': 4, 'b_min': 5, 'b_max': 6,
            'lux_min': 7, 'lux_max': 8, 'ir_min': 9, 'ir_max': 10,
        },
    )
    assert with_mux.get_config_summary() == (
        'MUX 0x70:2 I2C 0x29 — R 1–2, G 3–4, B 5–6, Lux 7–8, IR 9–10'
    )

    without_mux = TestStep.objects.create(
        suite=suite, step_type=TestStep.LED_SPECTRAL_READING, name='Read LED no MUX',
        config={
            'i2c_addr': '0x29',
            'r_min': 1, 'r_max': 2, 'g_min': 3, 'g_max': 4, 'b_min': 5, 'b_max': 6,
            'lux_min': 7, 'lux_max': 8, 'ir_min': 9, 'ir_max': 10,
        },
    )
    assert without_mux.get_config_summary() == (
        'I2C 0x29 — R 1–2, G 3–4, B 5–6, Lux 7–8, IR 9–10'
    )

    no_bounds = TestStep.objects.create(
        suite=suite, step_type=TestStep.LED_SPECTRAL_READING, name='Read LED no bounds',
        config={'mux_chan': '2', 'i2c_addr': '0x29'},
    )
    assert no_bounds.get_config_summary() == (
        'I2C 0x29 — R any, G any, B any, Lux any, IR any'
    )


@pytest.mark.django_db
def test_step_config_summary_operator_intervention(design):
    suite = TestSuite.objects.create(design=design, version=1)
    step = TestStep.objects.create(
        suite=suite, step_type=TestStep.OPERATOR_INTERVENTION, name='Connect probe',
        config={'message': 'Connect the probe to J3 before continuing.'},
    )
    assert step.get_config_summary() == 'Connect the probe to J3 before continuing.'

    empty = TestStep.objects.create(
        suite=suite, step_type=TestStep.OPERATOR_INTERVENTION, name='No message', config={},
    )
    assert empty.get_config_summary() == 'No message'

    long_message = TestStep.objects.create(
        suite=suite, step_type=TestStep.OPERATOR_INTERVENTION, name='Long',
        config={'message': 'x' * 100},
    )
    summary = long_message.get_config_summary()
    assert len(summary) == 80
    assert summary.endswith('...')


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


@pytest.mark.django_db
def test_step_form_beep_duration_defaults_but_doesnt_override_saved_value(design):
    suite = TestSuite.objects.create(design=design, version=1)

    fresh_step = TestStep.objects.create(suite=suite, step_type=TestStep.BEEP, name='Beep', config={'schema_version': 1})
    assert TestStepForm(instance=fresh_step)['duration_ms'].value() == 100

    configured_step = TestStep.objects.create(
        suite=suite, step_type=TestStep.BEEP, name='Beep 2', config={'duration_ms': 300, 'schema_version': 1},
    )
    assert TestStepForm(instance=configured_step)['duration_ms'].value() == 300


def test_step_type_choices_alphabetical_is_sorted_by_label():
    labels = [label for _, label in TestStep.STEP_TYPE_CHOICES_ALPHABETICAL]
    assert labels == sorted(labels)
    # Same set of types as the canonical (definition-order) choices, just reordered.
    assert set(TestStep.STEP_TYPE_CHOICES_ALPHABETICAL) == set(TestStep.STEP_TYPE_CHOICES)


@pytest.mark.django_db
def test_step_form_python_requires_code_and_validates_syntax():
    missing = TestStepForm(data={'step_type': TestStep.PYTHON, 'name': 'Script'})
    assert not missing.is_valid()
    assert 'python_code' in missing.errors

    invalid = TestStepForm(data={'step_type': TestStep.PYTHON, 'name': 'Script', 'python_code': 'def ('})
    assert not invalid.is_valid()
    assert 'python_code' in invalid.errors

    valid = TestStepForm(data={'step_type': TestStep.PYTHON, 'name': 'Script', 'python_code': 'print(1)'})
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data['config'] == {'python_code': 'print(1)'}


@pytest.mark.django_db
def test_step_form_iomod_analog_read_bounds_are_optional():
    form = TestStepForm(data={'step_type': TestStep.IOMOD_ANALOG_READ, 'name': 'Check', 'iomod': 'A', 'pin': '0'})
    assert form.is_valid(), form.errors
    assert form.cleaned_data['config'] == {'iomod': 'A', 'pin': '0'}


@pytest.mark.django_db
def test_step_form_iomod_digital_write_and_analog_write_use_distinct_config_keys():
    digital = TestStepForm(data={
        'step_type': TestStep.IOMOD_DIGITAL_WRITE, 'name': 'Set', 'iomod': 'C', 'pin': '4', 'digital_write': '1',
    })
    assert digital.is_valid(), digital.errors
    assert digital.cleaned_data['config'] == {'iomod': 'C', 'pin': '4', 'digital_write': '1'}

    analog = TestStepForm(data={
        'step_type': TestStep.IOMOD_ANALOG_WRITE, 'name': 'Set', 'iomod': 'D', 'pin': '5', 'analog_write': '200',
    })
    assert analog.is_valid(), analog.errors
    assert analog.cleaned_data['config'] == {'iomod': 'D', 'pin': '5', 'analog_write': 200}


def _led_spectral_reading_data(**overrides):
    data = {
        'step_type': TestStep.LED_SPECTRAL_READING, 'name': 'Read LED',
        'mux_chan': '2', 'i2c_addr': '0x29',
        'r_min': '1', 'r_max': '2', 'g_min': '3', 'g_max': '4', 'b_min': '5', 'b_max': '6',
        'lux_min': '7', 'lux_max': '8', 'ir_min': '9', 'ir_max': '10',
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_step_form_led_spectral_reading_requires_only_mux_chan_and_i2c_addr():
    form = TestStepForm(data=_led_spectral_reading_data())
    assert form.is_valid(), form.errors
    assert 'mux_addr' not in form.cleaned_data['config']

    missing_i2c = TestStepForm(data=_led_spectral_reading_data(i2c_addr=''))
    assert not missing_i2c.is_valid()
    assert 'i2c_addr' in missing_i2c.errors

    missing_chan = TestStepForm(data=_led_spectral_reading_data(mux_chan=''))
    assert not missing_chan.is_valid()
    assert 'mux_chan' in missing_chan.errors


@pytest.mark.django_db
def test_step_form_led_spectral_reading_min_max_bounds_are_optional():
    # A single bound left blank is simply omitted from config, not an error.
    one_missing = TestStepForm(data=_led_spectral_reading_data(g_max=''))
    assert one_missing.is_valid(), one_missing.errors
    assert 'g_max' not in one_missing.cleaned_data['config']
    assert one_missing.cleaned_data['config']['g_min'] == 3

    # All ten bounds left blank - still valid, just none of them end up in config.
    none_given = TestStepForm(data=_led_spectral_reading_data(
        r_min='', r_max='', g_min='', g_max='', b_min='', b_max='',
        lux_min='', lux_max='', ir_min='', ir_max='',
    ))
    assert none_given.is_valid(), none_given.errors
    assert none_given.cleaned_data['config'] == {'mux_chan': '2', 'i2c_addr': '0x29'}


@pytest.mark.django_db
def test_step_form_led_spectral_reading_accepts_mux_addr_and_validates_hex():
    valid = TestStepForm(data=_led_spectral_reading_data(mux_addr='0x70'))
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data['config']['mux_addr'] == '0x70'

    invalid = TestStepForm(data=_led_spectral_reading_data(mux_addr='not-hex'))
    assert not invalid.is_valid()
    assert 'mux_addr' in invalid.errors

    invalid_i2c = TestStepForm(data=_led_spectral_reading_data(i2c_addr='zz'))
    assert not invalid_i2c.is_valid()
    assert 'i2c_addr' in invalid_i2c.errors


@pytest.mark.django_db
def test_step_form_operator_intervention_requires_message():
    missing = TestStepForm(data={'step_type': TestStep.OPERATOR_INTERVENTION, 'name': 'Intervention'})
    assert not missing.is_valid()
    assert 'message' in missing.errors

    valid = TestStepForm(data={
        'step_type': TestStep.OPERATOR_INTERVENTION, 'name': 'Intervention',
        'message': 'Connect the probe to J3 before continuing.',
    })
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data['config'] == {'message': 'Connect the probe to J3 before continuing.'}


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


@pytest.mark.django_db
def test_step_form_i2c_addr_default_but_doesnt_override_saved_values(design):
    suite = TestSuite.objects.create(design=design, version=1)

    # A freshly-added step (empty config, as test_step_add creates it) shows the I2C Addr
    # default - it's required, so it needs *some* value.
    fresh_step = TestStep.objects.create(
        suite=suite, step_type=TestStep.LED_SPECTRAL_READING, name='Read LED', config={'schema_version': 1},
    )
    fresh_form = TestStepForm(instance=fresh_step)
    assert fresh_form['i2c_addr'].value() == '0x10'

    # An existing step with its own saved value keeps showing that, not the default.
    configured_step = TestStep.objects.create(
        suite=suite, step_type=TestStep.LED_SPECTRAL_READING, name='Read LED 2',
        config={'i2c_addr': '0x2a', 'mux_addr': '0x72', 'schema_version': 1},
    )
    configured_form = TestStepForm(instance=configured_step)
    assert configured_form['i2c_addr'].value() == '0x2a'


def test_step_form_mux_addr_has_a_placeholder_not_an_initial_value():
    """MUX Addr is genuinely optional, so "0x71" is shown as a greyed-out hint (HTML
    placeholder) rather than a real initial value - it must never appear in submitted data
    unless the user actually types it, unlike i2c_addr's real default above."""
    field = TestStepForm().fields['mux_addr']
    assert field.initial in (None, '')
    assert field.widget.attrs['placeholder'] == '0x71'


@pytest.mark.django_db
def test_step_form_mux_addr_left_blank_stays_blank_whether_or_not_previously_saved(design):
    suite = TestSuite.objects.create(design=design, version=1)

    fresh_step = TestStep.objects.create(
        suite=suite, step_type=TestStep.LED_SPECTRAL_READING, name='Read LED', config={'schema_version': 1},
    )
    assert TestStepForm(instance=fresh_step)['mux_addr'].value() in (None, '')

    # A step saved with MUX Addr deliberately left blank (no MUX on this board) must keep
    # showing it blank too (issue found live: it silently reappeared as "0x71" after a save).
    saved_step = TestStep.objects.create(
        suite=suite, step_type=TestStep.LED_SPECTRAL_READING, name='Read LED 2',
        config={'i2c_addr': '0x2a', 'mux_chan': '0', 'schema_version': 1},
    )
    saved_form = TestStepForm(instance=saved_step)
    assert saved_form['i2c_addr'].value() == '0x2a'
    assert saved_form['mux_addr'].value() in (None, '')
