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
