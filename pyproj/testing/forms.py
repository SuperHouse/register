# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
import ast

from django import forms
from django.core.validators import RegexValidator

from device.models import Design
from .models import Tester, TestModule, TestModuleType, TestStep

# Used by the LED Spectral Reading step's MUX Addr/I2C Addr fields (issue #109) - a bare hex
# string, with or without a "0x"/"0X" prefix.
hex_address_validator = RegexValidator(
    regex=r'^(0[xX])?[0-9A-Fa-f]+$', message='Enter a hex value, e.g. 70 or 0x70.',
)


class DesignChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.client.company_name} {obj.sku}: {obj.name} v{obj.hw_version}'


class TesterForm(forms.ModelForm):
    class Meta:
        model = Tester
        fields = ['name', 'version', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class TestModuleTypeForm(forms.ModelForm):
    class Meta:
        model = TestModuleType
        fields = ['name', 'version']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TestModuleForm(forms.ModelForm):
    class Meta:
        model = TestModule
        fields = ['module_type', 'notes']
        widgets = {
            'module_type': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CompatibleDesignAddForm(forms.Form):
    design = DesignChoiceField(
        queryset=Design.objects.filter(obsolete=False).select_related('client').order_by(
            'client__company_name', 'sku', 'name', 'hw_version'
        ),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, module_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Designs already compatible with this module type aren't offered again.
        if module_type is not None:
            self.fields['design'].queryset = self.fields['design'].queryset.exclude(
                pk__in=module_type.compatible_designs.values_list('pk', flat=True)
            )


class CopyTestStepsFromForm(forms.Form):
    """Backs the "Copy Test Suite from:" control at the bottom of the current Test Suite
    page: appends another Design's current Test Suite's steps (including their config) onto
    this one - see testing.views.test_suite_copy_steps_from."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    source_design = DesignChoiceField(
        queryset=Design.objects.filter(obsolete=False).select_related('client').order_by(
            'client__company_name', 'sku', 'name', 'hw_version'
        ),
        label='Copy Test Suite from',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, exclude_design=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Copying a design's steps onto itself would just duplicate them - not offered.
        if exclude_design is not None:
            self.fields['source_design'].queryset = self.fields['source_design'].queryset.exclude(pk=exclude_design.pk)


class TestSuiteSaveNewVersionForm(forms.Form):
    """Backs the "Save as New Version" action: freezes the current version's steps as a
    historical record (optionally noting what's in it) and starts the next version as an
    editable copy - see TestSuite's docstring and testing.views.test_suite_save_new_version."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    notes = forms.CharField(
        required=False, label='Notes',
        help_text='Optional - what does this version represent? Shown in the version history.',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )


class TestStepTypeAddForm(forms.Form):
    """Backs the suite edit page's drop-down + Add button for appending a new step of a
    chosen type (issue #101's suggested initial implementation, in place of a drag-and-drop
    palette)."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    step_type = forms.ChoiceField(choices=TestStep.STEP_TYPE_CHOICES_ALPHABETICAL, widget=forms.Select(attrs={'class': 'form-select'}))


class TestStepForm(forms.ModelForm):
    """A single form covering every step type's config fields; clean() picks out only the
    subset relevant to the selected step_type (see TYPE_FIELDS) and validates that type's
    required fields, rather than needing six separate forms/views per type. The template
    shows/hides each type's fieldset client-side based on the step_type dropdown."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    # Declared explicitly (rather than left to Meta/the model field) so its choices can be
    # alphabetical-by-label instead of TestStep.STEP_TYPE_CHOICES' definition order.
    step_type = forms.ChoiceField(choices=TestStep.STEP_TYPE_CHOICES_ALPHABETICAL,
                                   widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_step_type'}))

    delay_ms = forms.IntegerField(required=False, min_value=0, label='Delay (ms)',
                                   widget=forms.NumberInput(attrs={'class': 'form-control'}))

    upload_tool = forms.ChoiceField(required=False, choices=TestStep.UPLOAD_TOOL_CHOICES,
                                     widget=forms.Select(attrs={'class': 'form-select'}))
    # A live dropdown of available serial ports isn't possible from this web app - it has no
    # connection to the physical Tester that would eventually run this step - so this is
    # plain text for now (issue #101 asked for a drop-down; flagged as a deliberate
    # simplification rather than silently reinterpreted).
    port = forms.CharField(required=False, label='Serial Port / Device',
                            widget=forms.TextInput(attrs={'class': 'form-control'}))
    firmware_file = forms.CharField(required=False, label='Firmware Binary Image',
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))

    count = forms.IntegerField(required=False, min_value=1, initial=1, label='Count',
                                widget=forms.NumberInput(attrs={'class': 'form-control'}))
    duration_ms = forms.IntegerField(required=False, min_value=0, label='Duration (ms)',
                                      widget=forms.NumberInput(attrs={'class': 'form-control'}))

    rail = forms.ChoiceField(required=False, choices=TestStep.POWER_RAIL_CHOICES,
                              widget=forms.Select(attrs={'class': 'form-select'}))
    min_v = forms.FloatField(required=False, label='Min V',
                              widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}))
    max_v = forms.FloatField(required=False, label='Max V',
                              widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}))
    min_ma = forms.FloatField(required=False, label='Min mA',
                               widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}))
    max_ma = forms.FloatField(required=False, label='Max mA',
                               widget=forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}))

    action = forms.ChoiceField(required=False, choices=TestStep.RAIL_ACTION_CHOICES, widget=forms.RadioSelect)

    python_code = forms.CharField(required=False, label='Python Code',
                                   widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10,
                                                                 'style': 'font-family: monospace;'}))

    # Shared by all four IOMOD step types (issues #105-#108), same as `rail` above.
    iomod = forms.ChoiceField(required=False, label='IOMOD', choices=TestStep.IOMOD_CHOICES,
                               widget=forms.Select(attrs={'class': 'form-select'}))
    pin = forms.ChoiceField(required=False, label='Pin', choices=TestStep.IOMOD_PIN_CHOICES,
                             widget=forms.Select(attrs={'class': 'form-select'}))
    expect_min = forms.IntegerField(required=False, label='Expect Min',
                                     widget=forms.NumberInput(attrs={'class': 'form-control'}))
    expect_max = forms.IntegerField(required=False, label='Expect Max',
                                     widget=forms.NumberInput(attrs={'class': 'form-control'}))
    expect = forms.ChoiceField(required=False, label='Expect', choices=TestStep.BINARY_CHOICES,
                                widget=forms.RadioSelect)
    # Distinct field names/types for IOMOD Digital Write vs IOMOD Analog Write even though
    # both issues call this "Write" - one is a 0/1 radio pair, the other a free integer, so
    # they can't share a single form field.
    digital_write = forms.ChoiceField(required=False, label='Write', choices=TestStep.BINARY_CHOICES,
                                       widget=forms.RadioSelect)
    analog_write = forms.IntegerField(required=False, label='Write',
                                       widget=forms.NumberInput(attrs={'class': 'form-control'}))

    # LED Spectral Reading (issue #109). mux_chan reuses IOMOD_PIN_CHOICES - both are a plain
    # 0-7 selector, just for a different piece of hardware.
    # A placeholder, not an initial value: MUX Addr is genuinely optional (issue #109's "can
    # be null"), so this is shown greyed-out as a likely-value hint but is never part of the
    # submitted data unless the user actually types into the field, unlike i2c_addr's default
    # below (a real initial value, since I2C Addr is required and needs *some* value anyway).
    mux_addr = forms.CharField(required=False, label='MUX Addr', validators=[hex_address_validator],
                                widget=forms.TextInput(attrs={'class': 'form-control', 'style': 'max-width: 150px;',
                                                               'placeholder': '0x71'}))
    mux_chan = forms.ChoiceField(required=False, label='MUX Chan', choices=TestStep.IOMOD_PIN_CHOICES,
                                  widget=forms.Select(attrs={'class': 'form-select', 'style': 'max-width: 150px;'}))
    i2c_addr = forms.CharField(required=False, label='I2C Addr', initial='0x10', validators=[hex_address_validator],
                                widget=forms.TextInput(attrs={'class': 'form-control', 'style': 'max-width: 150px;'}))
    r_min = forms.IntegerField(required=False, label='RMin', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    r_max = forms.IntegerField(required=False, label='RMax', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    g_min = forms.IntegerField(required=False, label='GMin', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    g_max = forms.IntegerField(required=False, label='GMax', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    b_min = forms.IntegerField(required=False, label='BMin', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    b_max = forms.IntegerField(required=False, label='BMax', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    lux_min = forms.IntegerField(required=False, label='LuxMin', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    lux_max = forms.IntegerField(required=False, label='LuxMax', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    ir_min = forms.IntegerField(required=False, label='IRMin', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    ir_max = forms.IntegerField(required=False, label='IRMax', widget=forms.NumberInput(attrs={'class': 'form-control'}))

    # Maps each step type to the config fields it actually uses (a subset of the fields
    # declared above): 'required' fields must be filled for that type; 'optional' fields are
    # included in config only when given (their absence lets a consumer apply its own
    # default, e.g. Beep's count defaulting to 1).
    TYPE_FIELDS = {
        TestStep.DELAY: {'required': ['delay_ms'], 'optional': []},
        TestStep.UPLOAD_FIRMWARE: {'required': ['upload_tool', 'port', 'firmware_file'], 'optional': []},
        TestStep.BEEP: {'required': ['duration_ms'], 'optional': ['count']},
        TestStep.READ_RAIL_VOLTAGE: {'required': ['rail', 'min_v', 'max_v'], 'optional': []},
        TestStep.READ_RAIL_CURRENT: {'required': ['rail', 'min_ma', 'max_ma'], 'optional': []},
        TestStep.CONTROL_POWER_RAIL: {'required': ['rail', 'action'], 'optional': []},
        TestStep.PYTHON: {'required': ['python_code'], 'optional': []},
        TestStep.IOMOD_ANALOG_READ: {'required': ['iomod', 'pin'], 'optional': ['expect_min', 'expect_max']},
        TestStep.IOMOD_DIGITAL_READ: {'required': ['iomod', 'pin', 'expect'], 'optional': []},
        TestStep.IOMOD_DIGITAL_WRITE: {'required': ['iomod', 'pin', 'digital_write'], 'optional': []},
        TestStep.IOMOD_ANALOG_WRITE: {'required': ['iomod', 'pin', 'analog_write'], 'optional': []},
        TestStep.LED_SPECTRAL_READING: {
            'required': ['mux_chan', 'i2c_addr'],
            'optional': ['mux_addr', 'r_min', 'r_max', 'g_min', 'g_max',
                         'b_min', 'b_max', 'lux_min', 'lux_max', 'ir_min', 'ir_max'],
        },
    }

    class Meta:
        model = TestStep
        fields = ['step_type', 'name', 'hard_fail']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'hard_fail': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Seed the type-specific fields from the stored config; schema_version is never
            # user-facing.
            config = self.instance.config
            self.initial.update({k: v for k, v in config.items() if k != 'schema_version'})
            # A step whose config already has real values (i.e. it's been through this form
            # and saved at least once, as opposed to a fresh one straight from test_step_add,
            # whose config is just {'schema_version': ...}) must show a field it was saved
            # with left blank as blank - not silently resurface a field-level default (e.g.
            # mux_addr's "0x71") for a value the user deliberately cleared or never set.
            if any(k != 'schema_version' for k in config):
                for name, field in self.fields.items():
                    if field.initial and name not in config:
                        self.initial[name] = ''

    def clean(self):
        cleaned = super().clean()
        field_spec = self.TYPE_FIELDS.get(cleaned.get('step_type'))
        if field_spec is None:
            return cleaned

        config = {}
        for field_name in field_spec['required']:
            value = cleaned.get(field_name)
            if value in (None, ''):
                self.add_error(field_name, 'This field is required for this step type.')
            else:
                config[field_name] = value
        for field_name in field_spec['optional']:
            value = cleaned.get(field_name)
            if value not in (None, ''):
                config[field_name] = value

        # Cheap server-side typo-catcher for the Python step (issue #104): this app never
        # executes the code itself (it's stored config for external Testomatic hardware to
        # run later), so this only checks it parses, not that it's safe to run.
        if cleaned.get('step_type') == TestStep.PYTHON and 'python_code' in config:
            try:
                ast.parse(config['python_code'])
            except SyntaxError as e:
                self.add_error('python_code', f'Invalid Python syntax: {e}')

        cleaned['config'] = config
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        config = dict(self.cleaned_data.get('config', {}))
        config['schema_version'] = TestStep.CONFIG_SCHEMA_VERSION
        instance.config = config
        if commit:
            instance.save()
        return instance
