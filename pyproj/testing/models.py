# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 SuperHouse Automation Pty Ltd <info@superhouse.tv>
from django.db import models

from device.models import Design


class Tester(models.Model):
    """A physical Testomatic chassis that can be set up to test different board types."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} v{self.version}' if self.version else self.name


class TestModuleType(models.Model):
    """An abstract definition of a test module; may suit multiple designs (e.g. a revised
    design with unchanged test point locations can reuse the same module type)."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20, blank=True)
    compatible_designs = models.ManyToManyField(Design, blank=True, related_name='test_module_types')

    class Meta:
        ordering = ['name', 'version']

    def __str__(self):
        return f'{self.name} v{self.version}' if self.version else self.name


class TestModule(models.Model):
    """A physical test module (an instance of a TestModuleType) inserted into a Testomatic
    chassis to customise it for a specific target Device Under Test."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    module_type = models.ForeignKey(TestModuleType, on_delete=models.PROTECT, related_name='modules')
    notes = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['module_type__name', 'module_type__version', 'pk']

    def __str__(self):
        return f'#{self.pk} {self.module_type}'


class TestSuite(models.Model):
    """One version of a Design's Test Suite (issue #101) - an ordered list of TestSteps.
    Every Design has exactly one *current* Test Suite (the highest-`version` row for that
    design, possibly with zero steps if nothing has been configured yet - see
    `testing.views._get_or_create_current_suite`), which is freely editable in place; older
    versions are frozen historical records, created by the "Save as New Version" action
    (`testing.views.test_suite_save_new_version`), which copies the current version's steps
    onto a new row and leaves the old one untouched. Hardware revisioning lives on Design
    (hw_version, unique with sku), not on individual Devices, so a suite is scoped to a
    Design rather than to one physical serialized board."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    design = models.ForeignKey(Design, on_delete=models.CASCADE, related_name='test_suites')
    version = models.PositiveIntegerField(default=1)
    notes = models.TextField(null=True, blank=True)
    created_dt = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['design', '-version']
        constraints = [
            models.UniqueConstraint(fields=['design', 'version'], name='unique_design_test_suite_version'),
        ]

    def __str__(self):
        return f'{self.design} Test Suite v{self.version}'


class TestStep(models.Model):
    """A single step within a TestSuite, executed/examined in order (issue #101) - conceptually
    similar to a firewall rule list. Each step has a fixed type (below) with its own
    type-specific configuration fields, stored as JSON since the fields differ per type and
    this is the first genuinely polymorphic config shape in this codebase."""
    __test__ = False  # not a test class, despite the Test* name matching pytest's pattern

    DELAY = 'DELAY'
    UPLOAD_FIRMWARE = 'UPLOAD_FIRMWARE'
    BEEP = 'BEEP'
    READ_RAIL_VOLTAGE = 'READ_RAIL_VOLTAGE'
    READ_RAIL_CURRENT = 'READ_RAIL_CURRENT'
    CONTROL_POWER_RAIL = 'CONTROL_POWER_RAIL'
    PYTHON = 'PYTHON'
    IOMOD_ANALOG_READ = 'IOMOD_ANALOG_READ'
    IOMOD_DIGITAL_READ = 'IOMOD_DIGITAL_READ'
    IOMOD_DIGITAL_WRITE = 'IOMOD_DIGITAL_WRITE'
    IOMOD_ANALOG_WRITE = 'IOMOD_ANALOG_WRITE'
    STEP_TYPE_CHOICES = [
        (DELAY, 'Delay'),
        (UPLOAD_FIRMWARE, 'Upload Firmware'),
        (BEEP, 'Beep'),
        (READ_RAIL_VOLTAGE, 'Read Rail Voltage'),
        (READ_RAIL_CURRENT, 'Read Rail Current'),
        (CONTROL_POWER_RAIL, 'Control Power Rail'),
        (PYTHON, 'Python'),
        (IOMOD_ANALOG_READ, 'IOMOD Analog Read'),
        (IOMOD_DIGITAL_READ, 'IOMOD Digital Read'),
        (IOMOD_DIGITAL_WRITE, 'IOMOD Digital Write'),
        (IOMOD_ANALOG_WRITE, 'IOMOD Analog Write'),
    ]
    # Alphabetical-by-label rendering of the above, computed once rather than hand-sorted, so
    # this stays correct as more step types are added later without anyone remembering to
    # re-order STEP_TYPE_CHOICES itself. Used by the "Add" step-type dropdown and the step
    # edit page's Type dropdown; STEP_TYPE_CHOICES itself (definition order) still backs the
    # model field's `choices=` and the admin.
    STEP_TYPE_CHOICES_ALPHABETICAL = sorted(STEP_TYPE_CHOICES, key=lambda choice: choice[1])
    # Fixed per-type colour coding for the step's box header (issue #101) - types are
    # predefined by this codebase, not user-created rows, so (unlike ProductionStage.color)
    # there's no per-instance colour picker.
    STEP_TYPE_COLORS = {
        DELAY: '#6c757d',
        UPLOAD_FIRMWARE: '#0d6efd',
        BEEP: '#fd7e14',
        READ_RAIL_VOLTAGE: '#198754',
        READ_RAIL_CURRENT: '#20c997',
        CONTROL_POWER_RAIL: '#dc3545',
        PYTHON: '#6f42c1',
        IOMOD_DIGITAL_READ: '#0dcaf0',
        IOMOD_ANALOG_READ: '#0aa2c0',
        IOMOD_DIGITAL_WRITE: '#d63384',
        IOMOD_ANALOG_WRITE: '#ad1457',
    }
    # Placeholder rail names until this project integrates with Testomatic, which defines
    # power rails more fully.
    POWER_RAIL_CHOICES = [('3.3V', '3.3V'), ('5V', '5V'), ('12V', '12V')]
    # Placeholder IOMOD identifiers/pin numbers (issues #105-#108), same "hardcoded list
    # pending Testomatic integration" convention as POWER_RAIL_CHOICES above.
    IOMOD_CHOICES = [(letter, letter) for letter in 'ABCDEFG']
    IOMOD_PIN_CHOICES = [(str(n), str(n)) for n in range(8)]
    BINARY_CHOICES = [('0', '0'), ('1', '1')]
    UPLOAD_TOOL_CHOICES = [
        ('avrdude', 'avrdude'),
        ('esptool.py', 'esptool.py'),
        ('openocd', 'OpenOCD'),
        ('stm32cubeprogrammer', 'STM32CubeProgrammer'),
    ]
    RAIL_ACTION_ON = 'ON'
    RAIL_ACTION_OFF = 'OFF'
    RAIL_ACTION_CHOICES = [(RAIL_ACTION_ON, 'Turn On'), (RAIL_ACTION_OFF, 'Turn Off')]

    # Bumped whenever a step type's config shape changes; stored as a "schema_version" key
    # inside config itself (not just as a DB column) so it survives being exported/read
    # standalone by an external consumer, per issue #101's "enable programmatic
    # generation/modification via external scripts" requirement.
    CONFIG_SCHEMA_VERSION = 1

    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField(default=0)
    step_type = models.CharField(max_length=32, choices=STEP_TYPE_CHOICES)
    name = models.CharField(max_length=100)
    hard_fail = models.BooleanField(default=False)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.get_step_type_display()}: {self.name}'

    def get_color(self):
        return self.STEP_TYPE_COLORS.get(self.step_type, '#6c757d')

    def get_config_summary(self):
        """A short human-readable rendering of this step's config, for the suite edit page's
        second row (issue #101's "2 rows in a bordered box" layout)."""
        c = self.config
        if self.step_type == self.DELAY:
            return f"{c.get('delay_ms', '?')} ms"
        if self.step_type == self.UPLOAD_FIRMWARE:
            return f"{c.get('upload_tool', '?')} via {c.get('port', '?')} — {c.get('firmware_file', '?')}"
        if self.step_type == self.BEEP:
            return f"{c.get('count', 1)} × {c.get('duration_ms', '?')} ms"
        if self.step_type == self.READ_RAIL_VOLTAGE:
            return f"{c.get('rail', '?')}: {c.get('min_v', '?')}–{c.get('max_v', '?')} V"
        if self.step_type == self.READ_RAIL_CURRENT:
            return f"{c.get('rail', '?')}: {c.get('min_ma', '?')}–{c.get('max_ma', '?')} mA"
        if self.step_type == self.CONTROL_POWER_RAIL:
            return f"{c.get('rail', '?')}: {c.get('action', '?')}"
        if self.step_type == self.PYTHON:
            return self._python_code_summary(c.get('python_code', ''))
        if self.step_type == self.IOMOD_ANALOG_READ:
            return f"IOMOD {c.get('iomod', '?')} Pin {c.get('pin', '?')}: expect {self._range_summary(c.get('expect_min'), c.get('expect_max'))}"
        if self.step_type == self.IOMOD_DIGITAL_READ:
            return f"IOMOD {c.get('iomod', '?')} Pin {c.get('pin', '?')}: expect {c.get('expect', '?')}"
        if self.step_type == self.IOMOD_DIGITAL_WRITE:
            return f"IOMOD {c.get('iomod', '?')} Pin {c.get('pin', '?')}: write {c.get('digital_write', '?')}"
        if self.step_type == self.IOMOD_ANALOG_WRITE:
            return f"IOMOD {c.get('iomod', '?')} Pin {c.get('pin', '?')}: write {c.get('analog_write', '?')}"
        return ''

    @staticmethod
    def _range_summary(lo, hi):
        """Renders an optional (min, max) bound pair for the config summary - either bound
        may be absent ("or null", issue #105), meaning that side is unconstrained."""
        if lo is not None and hi is not None:
            return f"{lo}–{hi}"
        if lo is not None:
            return f"≥{lo}"
        if hi is not None:
            return f"≤{hi}"
        return 'any'

    @staticmethod
    def _python_code_summary(code):
        """A one-line rendering of a Python step's code for the config summary row, which is
        shared with the delete-confirm and frozen version-history pages and isn't built to
        hold a multi-line code block (issue #104)."""
        lines = [line for line in code.splitlines() if line.strip()]
        if not lines:
            return 'No code'
        first = lines[0].strip()
        if len(first) > 60:
            first = first[:57] + '...'
        remaining = len(lines) - 1
        if remaining:
            return f"{first} (+{remaining} more line{'s' if remaining != 1 else ''})"
        return first
